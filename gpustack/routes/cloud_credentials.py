from urllib.parse import urljoin
from functools import partial
import xml.etree.ElementTree as ET
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse

from gpustack.api.exceptions import (
    AlreadyExistsException,
    InternalServerErrorException,
    NotFoundException,
    ErrorResponse,
)
from gpustack.server.deps import SessionDep
from gpustack.schemas.clusters import (
    CloudCredentialCreate,
    CloudCredentialListParams,
    CloudCredentialPublic,
    CloudCredentialsPublic,
    CloudCredentialUpdate,
    CloudCredential,
    ClusterProvider,
)
from gpustack.cloud_providers.common import factory
from gpustack.routes.proxy import proxy_to

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_aws_xml_error(content: bytes) -> tuple[str, str]:
    """
    Parse AWS XML error response and extract error code and message.

    Args:
        content: Raw XML response bytes from AWS

    Returns:
        Tuple of (error_code, error_message)
    """
    try:
        root = ET.fromstring(content)
        # AWS error responses have format:
        # <Response><Errors><Error><Code>...</Code><Message>...</Message></Error></Errors>...</Response>
        # or <ErrorResponse><Error><Code>...</Code><Message>...</Message></Error></ErrorResponse>

        # Try Response/Errors/Error format first
        errors = root.find(".//Errors/Error")
        if errors is not None:
            code = errors.find("Code")
            message = errors.find("Message")
            if code is not None and message is not None:
                return code.text or "Unknown", message.text or "Unknown error"

        # Try ErrorResponse/Error format
        error = root.find(".//Error")
        if error is not None:
            code = error.find("Code")
            message = error.find("Message")
            if code is not None and message is not None:
                return code.text or "Unknown", message.text or "Unknown error"

        # Fallback: try to find any Code and Message elements
        code = root.find(".//Code")
        message = root.find(".//Message")
        if code is not None and message is not None:
            return code.text or "Unknown", message.text or "Unknown error"

    except ET.ParseError:
        pass

    return "Unknown", "Unable to parse AWS error response"


def _is_xml_content(content_type: str) -> bool:
    """Check if content type indicates XML response."""
    if not content_type:
        return False
    return "xml" in content_type.lower()


@router.get("", response_model=CloudCredentialsPublic)
async def list(
    session: SessionDep,
    params: CloudCredentialListParams = Depends(),
    name: str = None,
    search: str = None,
):
    fuzzy_fields = {}
    if search:
        fuzzy_fields = {"name": search}

    fields = {"deleted_at": None}
    if name:
        fields = {"name": name}

    if params.watch:
        return StreamingResponse(
            CloudCredential.streaming(fields=fields, fuzzy_fields=fuzzy_fields),
            media_type="text/event-stream",
        )

    return await CloudCredential.paginated_by_query(
        session=session,
        fields=fields,
        fuzzy_fields=fuzzy_fields,
        page=params.page,
        per_page=params.perPage,
        order_by=params.order_by,
    )


@router.get("/{id}", response_model=CloudCredentialPublic)
async def get(session: SessionDep, id: int):
    existing = await CloudCredential.one_by_id(session, id)
    if not existing or existing.deleted_at is not None:
        raise NotFoundException(message=f"cloud credential {id} not found")

    return existing


@router.post("", response_model=CloudCredentialPublic)
async def create(session: SessionDep, input: CloudCredentialCreate):
    existing = await CloudCredential.one_by_fields(
        session,
        {"deleted_at": None, "name": input.name},
    )
    if existing:
        raise AlreadyExistsException(
            message=f"cloud credential {input.name} already exists"
        )

    try:
        return await CloudCredential.create(session, input)
    except Exception as e:
        raise InternalServerErrorException(
            message=f"Failed to create cloud credential: {e}"
        )


@router.put("/{id}", response_model=CloudCredentialPublic)
async def update(session: SessionDep, id: int, input: CloudCredentialUpdate):
    existing = await CloudCredential.one_by_id(session, id)
    if not existing or existing.deleted_at is not None:
        raise NotFoundException(message=f"cloud credential {id} not found")

    try:
        await CloudCredential.update(existing, session=session, source=input)
    except Exception as e:
        raise InternalServerErrorException(
            message=f"Failed to update cloud credential: {e}"
        )

    return await CloudCredential.one_by_id(session, id)


@router.delete("/{id}")
async def delete(session: SessionDep, id: int):
    existing = await CloudCredential.one_by_id(session, id)
    if not existing or existing.deleted_at is not None:
        raise NotFoundException(message=f"cloud credential {id} not found")

    try:
        await existing.delete(session=session)
    except Exception as e:
        raise InternalServerErrorException(
            message=f"Failed to delete cloud credential: {e}"
        )


@router.api_route("/{id}/provider-proxy/{path:path}", methods=["GET"])
async def proxy_cluster_provider_api(
    request: Request, session: SessionDep, id: int, path: str
):
    """
    To support other provider in the future, use api_route instead of get.
    """

    credential = await CloudCredential.one_by_id(session=session, id=id)
    if not credential:
        raise NotFoundException(message=f"Credential {id} not found")
    if credential.provider in [ClusterProvider.Docker, ClusterProvider.Kubernetes]:
        raise NotFoundException(message=f"Provider {credential.provider} not supported")
    provider = factory.get(credential.provider, None)
    if provider is None:
        raise NotFoundException(message=f"Provider {credential.provider} not found")

    url = urljoin(provider[0].get_api_endpoint(), path)
    if request.query_params:
        url = f"{url}?{str(request.query_params)}"

    options = {
        **(credential.options or {}),
    }

    # Log debug information for AWS calls
    logger.debug(
        f"[AWS Provider Proxy] Credential ID: {id}, Provider: {credential.provider}"
    )
    logger.debug(f"[AWS Provider Proxy] Request path: {path}")
    logger.debug(f"[AWS Provider Proxy] Full URL: {url}")
    logger.debug(
        f"[AWS Provider Proxy] Credential key (first 10 chars): {credential.key[:10] if credential.key else 'None'}..."
    )
    logger.debug(f"[AWS Provider Proxy] Region: {options.get('region', 'us-east-1')}")
    logger.debug(f"[AWS Provider Proxy] Options: {options}")

    # Check if this is an AWS provider request - use aiobotocore for proper authentication
    if credential.provider == ClusterProvider.AWS:
        logger.debug("[AWS Provider Proxy] Using aiobotocore for AWS request")
        try:
            return await _handle_aws_proxy(request, credential, path, options)
        except Exception as e:
            logger.error(f"[AWS Provider Proxy] Error in _handle_aws_proxy: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={
                    "code": 500,
                    "reason": "InternalError",
                    "message": f"AWS proxy error: {str(e)}",
                },
            )

    # For non-AWS providers (DigitalOcean, etc.), use the generic proxy
    header_modifier = partial(
        provider[0].process_header, credential.key, credential.secret, options
    )

    logger.debug("[AWS Provider Proxy] Sending request via proxy_to...")
    response = await proxy_to(request, url, header_modifier)

    logger.debug(f"[AWS Provider Proxy] Response status: {response.status_code}")
    logger.debug(
        f"[AWS Provider Proxy] Response content-type: {response.headers.get('Content-Type', 'unknown')}"
    )
    logger.debug(
        f"[AWS Provider Proxy] Response body preview (first 500 chars): {response.body[:500] if response.body else 'empty'}"
    )

    # Check if the response is an XML error (AWS returns XML errors)
    content_type = response.headers.get("Content-Type", "")
    if _is_xml_content(content_type) and response.status_code >= 400:
        # Parse AWS XML error and convert to JSON format
        error_code, error_message = _parse_aws_xml_error(response.body)

        # Map AWS error codes to appropriate HTTP status codes
        status_code = response.status_code
        if response.status_code in [401, 403]:
            status_code = (
                400  # Convert to Bad Request for consistency with DigitalOcean
            )

        # Return JSON error response following GPUStack format
        error_response = ErrorResponse(
            code=status_code,
            reason=error_code,
            message=error_message,
        )
        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump(),
            headers={
                "X-GPUStack-Original-Status": str(response.status_code),
                "X-GPUStack-Original-Error-Code": error_code,
            },
        )

    if response.status_code in [401, 403, 404]:
        original_status = response.status_code
        response.status_code = 400
        response.headers.append("X-GPUStack-Original-Status", str(original_status))
    return response


# AWS proxy handler functions
async def _handle_aws_proxy(
    request: Request, credential: CloudCredential, path: str, options: dict
) -> JSONResponse:
    """Handle AWS-specific proxy requests using aiobotocore.

    This function uses aiobotocore to make AWS API calls with proper
    AWS Signature V4 authentication, avoiding the 401 AuthFailure errors
    that occur when using generic HTTP proxy.

    Args:
        request: FastAPI Request object
        credential: CloudCredential with AWS credentials
        path: URL path (e.g., "aws/regions", "aws/images")
        options: Additional options from credential (region, vpc, etc.)

    Returns:
        JSONResponse with AWS data
    """
    from gpustack.cloud_providers.aws import AWSClient
    from botocore.exceptions import (
        ClientError,
        NoCredentialsError,
        EndpointConnectionError,
    )

    region = options.get("region", "us-east-1")

    logger.debug(f"[AWS aiobotocore] Initializing client for region {region}")

    # Initialize AWSClient with aiobotocore
    aws_client = AWSClient(
        access_key=credential.key or "",
        secret_key=credential.secret or "",
        region=region,
        config=None,
    )

    try:
        # Route to specific endpoint handler
        if path == "aws/regions":
            logger.debug("[AWS aiobotocore] Calling get_regions()")
            regions = await aws_client.get_regions()
            result = {"regions": regions, "meta": {"total": len(regions)}}

        elif path == "aws/images":
            query_region = request.query_params.get("region", region)
            logger.debug(f"[AWS aiobotocore] Calling get_images({query_region})")
            images = await aws_client.get_images(region=query_region)
            result = {"images": images, "meta": {"total": len(images)}}

        elif path == "aws/instance-types":
            logger.debug("[AWS aiobotocore] Calling get_instance_types()")
            instance_types = await aws_client.get_instance_types(gpu_only=True)
            result = {
                "instance_types": instance_types,
                "meta": {"total": len(instance_types)},
            }

        else:
            logger.warning(f"[AWS aiobotocore] Unknown endpoint: {path}")
            return JSONResponse(
                status_code=404,
                content={
                    "code": 404,
                    "reason": "NotFound",
                    "message": f"Unknown AWS endpoint: {path}",
                },
            )

        logger.debug(f"[AWS aiobotocore] Success: {path}")
        return JSONResponse(status_code=200, content=result)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        logger.error(f"[AWS aiobotocore] ClientError: {error_code}")
        return JSONResponse(
            status_code=400,
            content={"code": 400, "reason": error_code, "message": error_msg},
            headers={"X-GPUStack-Original-Error-Code": error_code},
        )

    except NoCredentialsError:
        logger.error("[AWS aiobotocore] No credentials")
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "reason": "InvalidCredentials",
                "message": "AWS credentials are missing",
            },
        )

    except EndpointConnectionError as e:
        logger.error(f"[AWS aiobotocore] Connection error: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "reason": "ConnectionError",
                "message": "Cannot connect to AWS",
            },
        )

    except Exception as e:
        logger.error(f"[AWS aiobotocore] Unexpected error: {e}")
        return JSONResponse(
            status_code=500,
            content={"code": 500, "reason": "InternalError", "message": str(e)},
        )

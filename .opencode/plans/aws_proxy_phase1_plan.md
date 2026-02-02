# Plano de Implementação: AWS Provider-Proxy com aiobotocore

## Fase 1: Endpoint `aws/regions`

**Objetivo:** Implementar endpoint para listar regiões AWS usando aiobotocore, resolvendo o problema de autenticação 401.

---

## 1. Contexto do Problema

### Situação Atual
```
Frontend → GET /cloud-credentials/{id}/provider-proxy/aws/regions
    ↓
Backend → proxy_to() com aiohttp
    ↓
AWS → 401 AuthFailure (falta assinatura AWS SigV4)
```

### Solução Proposta
```
Frontend → GET /cloud-credentials/{id}/provider-proxy/aws/regions
    ↓
Backend → Detecta AWS → aiobotocore.describe_regions()
    ↓
AWS → 200 OK (com assinatura automática)
    ↓
Backend → Converte para JSON → Frontend
```

---

## 2. Arquivos a Modificar

### Arquivo 1: `gpustack/routes/cloud_credentials.py`

#### Modificação A: Importações adicionais
```python
# Adicionar ao topo do arquivo
from gpustack.schemas.aws import AWSConfig
from gpustack.cloud_providers.aws import AWSClient
```

#### Modificação B: Dispatcher AWS em `proxy_cluster_provider_api()`
**Local:** Linha ~191-213 (antes da chamada `proxy_to()`)

**Código atual:**
```python
header_modifier = partial(
    provider[0].process_header, credential.key, credential.secret, options
)

logger.debug("[AWS Provider Proxy] Sending request to AWS API...")
response = await proxy_to(request, url, header_modifier)
```

**Novo código:**
```python
# Verificar se é provider AWS e usar aiobotocore
if credential.provider == ClusterProvider.AWS:
    logger.debug("[AWS Provider Proxy] Using aiobotocore for AWS request...")
    return await _handle_aws_proxy(request, credential, path, options)

# Para outros providers (DigitalOcean, etc.), manter comportamento atual
header_modifier = partial(
    provider[0].process_header, credential.key, credential.secret, options
)

logger.debug("[AWS Provider Proxy] Sending request via proxy_to...")
response = await proxy_to(request, url, header_modifier)
```

#### Modificação C: Nova função `_handle_aws_proxy()`
**Local:** Após a função `proxy_cluster_provider_api()` (final do arquivo)

```python
async def _handle_aws_proxy(
    request: Request, 
    credential: CloudCredential, 
    path: str,
    options: dict
) -> Response:
    """Handle AWS-specific proxy requests using aiobotocore.
    
    This function replaces the generic proxy_to() for AWS provider,
    using aiobotocore which automatically handles AWS Signature V4
    authentication.
    
    Args:
        request: FastAPI Request object
        credential: CloudCredential with AWS credentials
        path: URL path (e.g., "aws/regions", "aws/images")
        options: Additional options from credential (region, vpc, etc.)
        
    Returns:
        JSONResponse with AWS data
    """
    region = options.get("region", "us-east-1")
    
    logger.debug(f"[AWS aiobotocore Proxy] Initializing AWS client for region {region}")
    
    # Create AWSConfig if we have VPC/subnet/security_group options
    aws_config = None
    if any(k in options for k in ["vpc_id", "subnet_id", "security_group_id"]):
        aws_config = AWSConfig(
            vpc_id=options.get("vpc_id"),
            subnet_id=options.get("subnet_id"),
            security_group_id=options.get("security_group_id"),
        )
    
    # Initialize AWSClient with aiobotocore
    aws_client = AWSClient(
        access_key=credential.key or "",
        secret_key=credential.secret or "",
        region=region,
        config=aws_config,
    )
    
    try:
        # Route to specific endpoint handler
        if path == "aws/regions":
            logger.debug("[AWS aiobotocore Proxy] Handling regions endpoint")
            result = await _get_aws_regions(aws_client)
        elif path == "aws/images":
            # Fase 2: Implementar
            return JSONResponse(
                status_code=501,
                content={"code": 501, "reason": "NotImplemented", "message": "aws/images not yet implemented"}
            )
        elif path == "aws/instance-types":
            # Fase 3: Implementar
            return JSONResponse(
                status_code=501,
                content={"code": 501, "reason": "NotImplemented", "message": "aws/instance-types not yet implemented"}
            )
        else:
            logger.warning(f"[AWS aiobotocore Proxy] Unknown AWS endpoint: {path}")
            return JSONResponse(
                status_code=404,
                content={"code": 404, "reason": "NotFound", "message": f"Unknown AWS endpoint: {path}"}
            )
        
        logger.debug(f"[AWS aiobotocore Proxy] Successfully handled {path}")
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        logger.error(f"[AWS aiobotocore Proxy] Error handling {path}: {e}")
        return _convert_aws_exception_to_response(e)
```

#### Modificação D: Função `_get_aws_regions()`
**Local:** Após `_handle_aws_proxy()`

```python
async def _get_aws_regions(aws_client: AWSClient) -> dict:
    """Get AWS regions using aiobotocore and transform to JSON format.
    
    Calls EC2 describe_regions() and converts the response to a
    DigitalOcean-compatible JSON format for the frontend.
    
    Args:
        aws_client: Initialized AWSClient with valid credentials
        
    Returns:
        Dict with regions list and metadata
    """
    logger.debug("[AWS aiobotocore Proxy] Calling describe_regions()")
    
    async with aws_client._get_client() as client:
        response = await client.describe_regions()
        
        regions = []
        for region_data in response.get("Regions", []):
            region_name = region_data.get("RegionName", "")
            endpoint = region_data.get("Endpoint", "")
            opt_in_status = region_data.get("OptInStatus", "opt-in-not-required")
            
            regions.append({
                "slug": region_name,
                "name": region_name,
                "endpoint": endpoint,
                "opt_in_status": opt_in_status,
                "available": opt_in_status == "opt-in-not-required"
            })
        
        result = {
            "regions": regions,
            "meta": {
                "total": len(regions)
            }
        }
        
        logger.debug(f"[AWS aiobotocore Proxy] Found {len(regions)} regions")
        return result
```

#### Modificação E: Função de erro `_convert_aws_exception_to_response()`
**Local:** Após `_get_aws_regions()`

```python
def _convert_aws_exception_to_response(error: Exception) -> JSONResponse:
    """Convert AWS/botocore exceptions to GPUStack JSON error format.
    
    Args:
        error: Exception raised by aiobotocore/botocore
        
    Returns:
        JSONResponse with standardized error format
    """
    from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
    
    if isinstance(error, ClientError):
        error_code = error.response["Error"]["Code"]
        error_msg = error.response["Error"]["Message"]
        
        # Map AWS error codes to HTTP status
        status_map = {
            "AuthFailure": 400,
            "UnauthorizedOperation": 400,
            "InvalidParameterValue": 400,
            "InvalidAccessKeyId": 400,
            "SignatureDoesNotMatch": 400,
        }
        
        status_code = status_map.get(error_code, 500)
        
        logger.error(f"[AWS aiobotocore Proxy] AWS ClientError: {error_code} - {error_msg}")
        
        return JSONResponse(
            status_code=status_code,
            content={
                "code": status_code,
                "reason": error_code,
                "message": error_msg
            },
            headers={
                "X-GPUStack-Original-Error-Code": error_code
            }
        )
    
    elif isinstance(error, NoCredentialsError):
        logger.error("[AWS aiobotocore Proxy] No credentials provided")
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "reason": "InvalidCredentials",
                "message": "AWS credentials are missing or incomplete"
            }
        )
    
    elif isinstance(error, EndpointConnectionError):
        logger.error(f"[AWS aiobotocore Proxy] Connection error: {error}")
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "reason": "ConnectionError",
                "message": "Cannot connect to AWS EC2 API. Please check your network connection."
            }
        )
    
    else:
        logger.error(f"[AWS aiobotocore Proxy] Unexpected error: {error}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "reason": "InternalError",
                "message": str(error)
            }
        )
```

---

## 3. Testes de Validação

### Teste 1: Verificar endpoint responde
```bash
# 1. Iniciar GPUStack (você forneceu o comando)
uv run gpustack start --database-url "..." --gateway-mode disabled --api-port 8090 --data-dir ./data --debug

# 2. Testar endpoint
curl -s http://0.0.0.0:8090/v2/cloud-credentials/8/provider-proxy/aws/regions | jq .

# Esperado (JSON formatado):
{
  "regions": [
    {"slug": "us-east-1", "name": "us-east-1", ...},
    {"slug": "us-west-2", "name": "us-west-2", ...}
  ],
  "meta": {"total": 25}
}

# NÃO deve retornar XML 401 AuthFailure
```

### Teste 2: Verificar logs de debug
```bash
# No console deve aparecer:
[AWS Provider Proxy] Credential ID: 8, Provider: ClusterProvider.AWS
[AWS Provider Proxy] Using aiobotocore for AWS request...
[AWS aiobotocore Proxy] Initializing AWS client for region us-east-1
[AWS aiobotocore Proxy] Handling regions endpoint
[AWS aiobotocore Proxy] Calling describe_regions()
[AWS aiobotocore Proxy] Found 25 regions
[AWS aiobotocore Proxy] Successfully handled aws/regions
```

### Teste 3: Verificar DigitalOcean ainda funciona
```bash
# Testar que DigitalOcean não foi quebrado
curl -s http://0.0.0.0:8090/v2/cloud-credentials/{do_id}/provider-proxy/... 
# Deve continuar funcionando normalmente
```

---

## 4. Checklist de Implementação

### Preparação
- [ ] Backup do banco de dados (ou usar ambiente de teste)
- [ ] Verificar que as credenciais AWS funcionam via CLI
- [ ] Ter o frontend disponível para testar

### Modificações de Código
- [ ] Adicionar importações necessárias em `cloud_credentials.py`
- [ ] Implementar dispatcher AWS em `proxy_cluster_provider_api()`
- [ ] Criar função `_handle_aws_proxy()`
- [ ] Criar função `_get_aws_regions()`
- [ ] Criar função `_convert_aws_exception_to_response()`
- [ ] Verificar que logs de debug são gerados

### Testes
- [ ] Endpoint `aws/regions` retorna JSON 200
- [ ] Endpoint `aws/regions` não retorna 401
- [ ] Logs mostram aiobotocore sendo usado
- [ ] DigitalOcean continua funcionando (não foi quebrado)
- [ ] Erros AWS são convertidos para JSON (testar com credenciais inválidas)

### Commit
- [ ] `git add gpustack/routes/cloud_credentials.py`
- [ ] Commit message: "feat(aws-proxy): implement aiobotocore for aws/regions endpoint"

---

## 5. Próximas Fases (Pós-Validação)

### Fase 2: `aws/images` (~4h)
Implementar listagem de Deep Learning AMIs
- Filtros: Deep Learning AMI GPU Ubuntu 22.04
- Resposta: AMI ID, nome, descrição, região

### Fase 3: `aws/instance-types` (~4h)
Implementar listagem de tipos GPU
- Filtros: p3, p4d, g4dn, g5
- Resposta: slug, vcpus, memória, GPUs, tipo GPU

---

## 6. Riscos e Mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Quebrar DigitalOcean | Baixa | Alto | Manter `proxy_to()` para providers != AWS |
| Erro de importação | Média | Médio | Verificar imports de `AWSConfig` e `AWSClient` |
| aiobotocore não instalado | Baixa | Alto | Já é dependência do projeto (verificar) |
| Timeout AWS | Média | Baixo | Adicionar timeout config no boto_config |

---

## 7. Estimativa de Tempo

| Atividade | Tempo Estimado |
|-----------|---------------|
| Modificar `cloud_credentials.py` | 1.5h |
| Testes locais | 1h |
| Ajustes e debugging | 0.5h |
| **Total Fase 1** | **~3h** |

---

## 8. Critérios de Sucesso

✅ **Sucesso:** Endpoint `aws/regions` retorna JSON com lista de regiões
✅ **Sucesso:** Não há mais erro 401 AuthFailure
✅ **Sucesso:** DigitalOcean continua funcionando
✅ **Sucesso:** Logs mostram uso de aiobotocore

❌ **Falha:** Ainda recebe 401
❌ **Falha:** DigitalOcean quebrado
❌ **Falha:** Erros não são convertidos para JSON

---

## 9. Comando de Execução (para o Usuário)

Após aprovar o plano, execute:

```bash
# 1. Iniciar backend com debug
uv run gpustack start \
  --database-url "postgresql://neondb_owner:npg_8fQ0IUJdpwyi@ep-crimson-mouse-ahtgvc6g-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" \
  --gateway-mode disabled \
  --api-port 8090 \
  --data-dir ./data \
  --debug

# 2. Em outro terminal, testar
curl http://0.0.0.0:8090/v2/cloud-credentials/8/provider-proxy/aws/regions

# 3. Ver logs no terminal do gpustack
```

---

## 10. Aprovação

**Status:** ⏳ Aguardando aprovação do usuário

**Próximo passo:** Após você aprovar este plano, sairei do Plan Mode e implementarei as mudanças.

**Confirmação necessária:** 
- [ ] Plano revisado e aprovado
- [ ] Pronto para implementação
- [ ] Começar Fase 1 agora

---

**Documento preparado em:** 2026-02-02
**Versão:** 1.0
**Status:** Aguardando aprovação para execução

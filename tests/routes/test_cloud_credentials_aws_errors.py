"""Test AWS XML error parsing in cloud_credentials route."""

from gpustack.routes.cloud_credentials import _parse_aws_xml_error, _is_xml_content


class TestAWSXMLErrorParsing:
    """Test suite for AWS XML error parsing functions."""

    def test_parse_aws_xml_error_standard_format(self):
        """Test parsing standard AWS XML error format."""
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Errors>
                <Error>
                    <Code>AuthFailure</Code>
                    <Message>AWS was not able to validate the provided access credentials</Message>
                </Error>
            </Errors>
            <RequestID>ce900502-427a-4643-ac5e-d670434dea8a</RequestID>
        </Response>"""

        error_code, error_message = _parse_aws_xml_error(xml_content)

        assert error_code == "AuthFailure"
        assert (
            error_message
            == "AWS was not able to validate the provided access credentials"
        )

    def test_parse_aws_xml_error_errorresponse_format(self):
        """Test parsing AWS ErrorResponse format."""
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ErrorResponse>
            <Error>
                <Code>InvalidAccessKeyId</Code>
                <Message>The AWS Access Key Id you provided does not exist in our records.</Message>
            </Error>
            <RequestId>abc123</RequestId>
        </ErrorResponse>"""

        error_code, error_message = _parse_aws_xml_error(xml_content)

        assert error_code == "InvalidAccessKeyId"
        assert "does not exist in our records" in error_message

    def test_parse_aws_xml_error_invalid_xml(self):
        """Test handling of invalid XML."""
        xml_content = b"This is not XML at all"

        error_code, error_message = _parse_aws_xml_error(xml_content)

        assert error_code == "Unknown"
        assert "Unable to parse" in error_message

    def test_parse_aws_xml_error_empty_content(self):
        """Test handling of empty content."""
        xml_content = b""

        error_code, error_message = _parse_aws_xml_error(xml_content)

        assert error_code == "Unknown"
        assert "Unable to parse" in error_message

    def test_parse_aws_xml_error_missing_elements(self):
        """Test handling of XML without Code/Message elements."""
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <SomeOtherElement>value</SomeOtherElement>
        </Response>"""

        error_code, error_message = _parse_aws_xml_error(xml_content)

        assert error_code == "Unknown"
        assert "Unable to parse" in error_message


class TestIsXMLContent:
    """Test suite for XML content type detection."""

    def test_is_xml_content_application_xml(self):
        """Test detection of application/xml content type."""
        assert _is_xml_content("application/xml") is True

    def test_is_xml_content_text_xml(self):
        """Test detection of text/xml content type."""
        assert _is_xml_content("text/xml") is True

    def test_is_xml_content_with_charset(self):
        """Test detection of XML with charset."""
        assert _is_xml_content("application/xml; charset=utf-8") is True

    def test_is_xml_content_json(self):
        """Test rejection of JSON content type."""
        assert _is_xml_content("application/json") is False

    def test_is_xml_content_empty(self):
        """Test handling of empty content type."""
        assert _is_xml_content("") is False
        assert _is_xml_content(None) is False

    def test_is_xml_content_case_insensitive(self):
        """Test case insensitivity."""
        assert _is_xml_content("Application/XML") is True
        assert _is_xml_content("TEXT/XML") is True

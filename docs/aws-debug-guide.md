# AWS Integration Debug Guide

This guide explains how to debug AWS authentication and API call issues in GPUStack.

## 🔍 Enabling Debug Logs

### Start GPUStack with Debug Flag

```bash
gpustack start --debug
```

Or if running via Python:

```bash
python -m gpustack start --debug
```

### What Will Be Logged

When debug mode is active, you will see detailed logs like:

```
[AWS Provider Proxy] Credential ID: 5, Provider: AWS
[AWS Provider Proxy] Request path: aws/images
[AWS Provider Proxy] Full URL: https://ec2.amazonaws.com/aws/images?per_page=200
[AWS Provider Proxy] Credential key (first 10 chars): AKIAxxxxxxxx...
[AWS Provider Proxy] Region: us-east-1
[AWS Provider Proxy] Options: {'region': 'us-east-1', 'vpc_id': 'vpc-xxx', ...}
[AWS Provider Proxy] Sending request to AWS API...
[Proxy] GET https://ec2.amazonaws.com/aws/images?per_page=200
[Proxy] Headers: {'Authorization': 'Bearer ...', 'Content-Type': 'application/json'}
[Proxy] Response status: 401
[Proxy] Response body: <?xml version="1.0"...>
[AWS Provider Proxy] Response status: 401
```

## 🔧 Common Issues

### 1. AuthFailure - Invalid Credentials

**Symptom:**
```json
{
  "code": 400,
  "reason": "AuthFailure",
  "message": "AWS was not able to validate the provided access credentials"
}
```

**Possible Causes:**
- Incorrect Access Key ID
- Incorrect Secret Access Key
- Expired or revoked credentials
- Wrong region

**Debug Steps:**
1. Check the log: `[AWS Provider Proxy] Credential key (first 10 chars)`
2. Confirm the first characters match your AWS Access Key
3. Verify the region is correct in the logs

**Solution:**
- Re-create the credential in AWS IAM Console
- Verify the key is active (not expired)
- Ensure you are using the correct region (e.g., us-east-1)

### 2. InvalidAccessKeyId

**Symptom:**
```json
{
  "code": 400,
  "reason": "InvalidAccessKeyId",
  "message": "The AWS Access Key Id you provided does not exist in our records."
}
```

**Cause:** The Access Key was deleted or never existed.

**Solution:** Create a new Access Key in the AWS IAM Console.

### 3. Invalid Request Endpoint

**Symptom:** The proxy is calling `https://ec2.amazonaws.com/aws/images` but should be calling the EC2 API directly.

**Verification:** In the log `[Proxy] GET https://...`, confirm the endpoint.

**Known Issue:** The current provider-proxy implementation for AWS uses a generic endpoint. AWS requires:
1. Regional endpoints (e.g., `ec2.us-east-1.amazonaws.com`)
2. AWS Signature V4 on all requests

**Workaround:** To list images, you can test directly via AWS CLI:

```bash
aws ec2 describe-images \
  --region us-east-1 \
  --owners amazon \
  --filters "Name=name,Values=Deep Learning*" \
  --query 'Images[*].[ImageId,Name]' \
  --output table
```

## 🔬 Testing Authentication

### Test 1: Validate Credentials

Check the logs for:
```
[AWS Provider Proxy] Credential key (first 10 chars): AKIAxxxxxxxx...
```

Verify it matches your key:
```bash
echo "Your key: AKIA..."
```

### Test 2: Test with AWS CLI

```bash
# Configure AWS CLI with the same credentials as GPUStack
aws configure
# AWS Access Key ID [None]: AKIAxxxxxxxxxxxxxxxx
# AWS Secret Access Key [None]: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Default region name [None]: us-east-1

# Test authentication
aws sts get-caller-identity

# Should return:
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

### Test 3: Verify EC2 Permissions

```bash
# Test if you have EC2 permissions
aws ec2 describe-regions

# If this works, authentication is OK
```

## 🐛 Advanced Debugging

### Adding More Logs

To add additional logs, edit the file:

```python
# gpustack/routes/cloud_credentials.py

# Add where you need more info:
logger.debug(f"[Debug] Specific value: {variable}")
```

### Checking Headers

In the log `[Proxy] Headers`, verify the `Authorization` header is present and correct.

**For AWS:**
- The header should contain `AWS4-HMAC-SHA256` (AWS Signature V4)
- Or `Bearer` for proxy calls (current implementation)

**Note:** The current implementation does not automatically sign AWS requests. The proxy only sends basic headers.

## 📋 Validation Checklist

- [ ] Access Key ID starts with `AKIA` (IAM user) or `ASIA` (temporary credentials)
- [ ] Secret Access Key has 40 characters
- [ ] Region is in correct format (e.g., `us-east-1`)
- [ ] Credential is not expired in AWS Console
- [ ] IAM user has `AmazonEC2FullAccess` permissions
- [ ] AWS CLI test works
- [ ] Logs show the correct key in the first 10 characters

## 🆘 Still Having Issues?

If debug logs do not appear:

1. Check Python log level:
   ```python
   # At the beginning of gpustack/routes/cloud_credentials.py
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Verify logger is configured:
   ```bash
   # Look in the code for:
   logger = logging.getLogger(__name__)
   ```

3. Use temporary print (not recommended for production):
   ```python
   print(f"[DEBUG] Value: {variable}")
   ```

## 📝 Technical Notes

### How provider-proxy Works

1. Frontend calls: `GET /v2/cloud-credentials/{id}/provider-proxy/aws/images`
2. Backend retrieves the credential from the database
3. Backend builds the URL: `https://ec2.amazonaws.com/aws/images`
4. Backend calls `proxy_to()` with processed headers
5. `proxy_to()` makes the HTTP request via `aiohttp`
6. Response is returned to the frontend (JSON or converted XML)

### Known Limitations

The current AWS provider-proxy implementation does NOT:
- Automatically implement AWS Signature V4 in header_modifier
- Use regional EC2 endpoints
- Handle AWS response pagination

For full EC2 operations, use AWSClient directly instead of provider-proxy.

## ⚠️ Security Notice

**Never commit AWS credentials to git!** Always:
- Use environment variables for credentials
- Add credential files to `.gitignore`
- Rotate (revoke and recreate) credentials immediately if accidentally exposed

### If Credentials Are Exposed

1. **Revoke immediately** in AWS IAM Console:
   - Go to IAM > Users > [Your User] > Security credentials
   - Find the exposed Access Key
   - Click "Make inactive" or "Delete"

2. **Create new credentials**:
   - Click "Create access key"
   - Update GPUStack with the new credentials

3. **Check CloudTrail logs** for unauthorized usage:
   - Go to CloudTrail > Event history
   - Look for suspicious activity

4. **Audit affected resources**:
   - Check if any EC2 instances were created
   - Review billing for unexpected charges

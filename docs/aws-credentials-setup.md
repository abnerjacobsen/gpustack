# AWS Credentials Setup Guide for GPUStack

This guide explains how to create AWS IAM credentials with the necessary permissions for GPUStack and validate them before use.

## Prerequisites

- AWS account with administrative access
- AWS CLI installed and configured (optional, for testing)
- Access to AWS IAM Console: https://console.aws.amazon.com/iam/

## Step 1: Create IAM Policy

### 1.1 Navigate to IAM Policies

1. Log in to AWS Console: https://console.aws.amazon.com/
2. Go to **Services** > **IAM** (or search for "IAM")
3. In the left sidebar, click **Policies**
4. Click **Create policy**

### 1.2 Create GPUStack Policy

1. Click the **JSON** tab
2. Paste the following policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "GPUStackEC2Operations",
            "Effect": "Allow",
            "Action": [
                "ec2:RunInstances",
                "ec2:TerminateInstances",
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:DescribeRegions",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeImages",
                "ec2:DescribeInstanceTypes",
                "ec2:DescribeKeyPairs",
                "ec2:ImportKeyPair",
                "ec2:CreateKeyPair",
                "ec2:DeleteKeyPair",
                "ec2:CreateTags",
                "ec2:DescribeTags"
            ],
            "Resource": "*"
        },
        {
            "Sid": "GPUStackNetworkOperations",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeNetworkInterfaces",
                "ec2:AssociateAddress"
            ],
            "Resource": "*"
        },
        {
            "Sid": "GPUStackEBSOperations",
            "Effect": "Allow",
            "Action": [
                "ec2:CreateVolume",
                "ec2:DeleteVolume",
                "ec2:AttachVolume",
                "ec2:DetachVolume",
                "ec2:DescribeVolumes",
                "ec2:DescribeVolumeStatus"
            ],
            "Resource": "*"
        }
    ]
}
```

3. Click **Next: Tags**
4. (Optional) Add tags like:
   - Key: `Environment`, Value: `GPUStack`
   - Key: `ManagedBy`, Value: `IAM`
5. Click **Next: Review**
6. Enter policy details:
   - **Policy name**: `GPUStackEC2FullAccess`
   - **Description**: `Full EC2 access for GPUStack AWS integration including instances, key pairs, and EBS volumes`
7. Click **Create policy**

## Step 2: Create IAM User

### 2.1 Create New User

1. In IAM Console, click **Users** in the left sidebar
2. Click **Add users**
3. Configure user details:
   - **User name**: `gpustack-aws-user` (or your preferred name)
   - **Access type**: ☑️ **Programmatic access** (required for API/CLI)
   - ❌ Uncheck "AWS Management Console access"
4. Click **Next: Permissions**

### 2.2 Attach Policy

1. Select **Attach existing policies directly**
2. Search for `GPUStackEC2FullAccess`
3. ☑️ Check the box next to your policy
4. (Optional) Also attach `AmazonEC2FullAccess` for additional safety
5. Click **Next: Tags**
6. (Optional) Add tags
7. Click **Next: Review**
8. Review the configuration:
   - User name: `gpustack-aws-user`
   - Access type: Programmatic access
   - Permissions: GPUStackEC2FullAccess
9. Click **Create user**

### 2.3 Save Credentials

**⚠️ IMPORTANT: This is the only time you'll see the secret key!**

1. **Download .csv** button - Save the file securely
2. Or copy manually:
   - **Access key ID**: `AKIA...` (20 characters)
   - **Secret access key**: `XXXXXXXX...` (40 characters)

**Security best practices:**
- Store in password manager or secure vault
- Never commit to git or share via email
- Rotate keys every 90 days

## Step 3: Validate Credentials

Before using in GPUStack, validate the credentials with these tests:

### Option A: Using AWS CLI (Recommended)

Configure AWS CLI:

```bash
aws configure
# AWS Access Key ID [None]: AKIAxxxxxxxxxxxxxxxx
# AWS Secret Access Key [None]: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Default region name [None]: us-east-1
# Default output format [None]: json
```

Run validation tests:

```bash
#!/bin/bash
# AWS Credentials Validation Script for GPUStack

export AWS_REGION=us-east-1

echo "=== GPUStack AWS Credentials Validation ==="
echo ""

# Test 1: Basic credential validation
echo "Test 1: Credential validation..."
aws sts get-caller-identity > /dev/null 2>&1 && echo "✓ Credentials valid" || echo "✗ Invalid credentials"

# Test 2: Describe regions (lightweight test)
echo -e "\nTest 2: Describe regions..."
aws ec2 describe-regions --region-names $AWS_REGION > /dev/null 2>&1 && echo "✓ Can describe regions" || echo "✗ Cannot describe regions"

# Test 3: List AMIs (read-only)
echo -e "\nTest 3: List Deep Learning AMIs..."
aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=Deep Learning AMI (Ubuntu 22.04)*" \
  --query 'Images[0].[ImageId,Name]' \
  --region $AWS_REGION > /dev/null 2>&1 && echo "✓ Can list AMIs" || echo "✗ Cannot list AMIs"

# Test 4: Key pair operations
echo -e "\nTest 4: Key pair operations..."
aws ec2 create-key-pair --key-name test-gpustack-key --region $AWS_REGION > /dev/null 2>&1 && echo "✓ Can create key pairs" || echo "✗ Cannot create key pairs"
aws ec2 delete-key-pair --key-name test-gpustack-key --region $AWS_REGION > /dev/null 2>&1 && echo "✓ Can delete key pairs" || echo "✗ Cannot delete key pairs"

# Test 5: Run instances (dry-run)
echo -e "\nTest 5: Run instances (dry-run)..."
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t2.micro \
  --region $AWS_REGION \
  --dry-run 2>&1 | grep -q "Request would have succeeded" && echo "✓ Can run instances (dry-run)" || echo "✗ Cannot run instances"

# Test 6: EBS volumes (dry-run)
echo -e "\nTest 6: Create volumes (dry-run)..."
aws ec2 create-volume \
  --size 10 \
  --region $AWS_REGION \
  --availability-zone ${AWS_REGION}a \
  --volume-type gp3 \
  --dry-run 2>&1 | grep -q "Request would have succeeded" && echo "✓ Can create volumes (dry-run)" || echo "✗ Cannot create volumes"

echo -e "\n=== Validation Complete ==="
echo "If all tests show ✓, your credentials are ready for GPUStack!"
```

### Expected Output

All tests should show ✓:

```
=== GPUStack AWS Credentials Validation ===

Test 1: Credential validation...
✓ Credentials valid

Test 2: Describe regions...
✓ Can describe regions

Test 3: List Deep Learning AMIs...
✓ Can list AMIs

Test 4: Key pair operations...
✓ Can create key pairs
✓ Can delete key pairs

Test 5: Run instances (dry-run)...
✓ Can run instances (dry-run)

Test 6: Create volumes (dry-run)...
✓ Can create volumes (dry-run)

=== Validation Complete ===
If all tests show ✓, your credentials are ready for GPUStack!
```

### Option B: Manual Testing

If you don't have AWS CLI, manually verify in AWS Console:

1. **IAM Console**: Verify the user has `GPUStackEC2FullAccess` policy attached
2. **EC2 Console**: Check you can view:
   - Instances page (shows `ec2:DescribeInstances`)
   - Key Pairs page (shows `ec2:DescribeKeyPairs`)
   - Volumes page (shows `ec2:DescribeVolumes`)

## Step 4: Add to GPUStack

### 4.1 Open GPUStack UI

1. Log in to your GPUStack instance
2. Navigate to **Cloud Credentials** (or **Settings** > **Cloud Providers**)

### 4.2 Create AWS Credential

1. Click **Add Credential** or **Create Cloud Credential**
2. Fill in the form:
   - **Name**: `aws-production` (or descriptive name)
   - **Description**: `AWS credentials for GPU workers`
   - **Provider**: ☑️ **AWS**
   - **Access Key ID**: Paste your Access Key (AKIA...)
   - **Secret Access Key**: Paste your Secret Key
   - **Region**: Select your region (e.g., `us-east-1`)
   - **VPC ID** (optional): Leave blank for default VPC
   - **Subnet ID** (optional): Leave blank for default subnet
   - **Security Group ID** (optional): Leave blank for default

3. Click **Save** or **Create**

### 4.3 Validate in GPUStack

1. The credential should appear in the list
2. Status should show as **Valid** or **Active**
3. If available, click **Test** or **Validate** button to verify connectivity

## Troubleshooting

### Issue: "UnauthorizedOperation" Error

**Symptom:**
```
An error occurred (UnauthorizedOperation) when calling the CreateKeyPair operation
```

**Solution:**
- Missing permission in policy
- Update the IAM policy to include the specific action
- Common missing permissions: `ec2:CreateKeyPair`, `ec2:CreateTags`

### Issue: "Access Denied" for Specific Region

**Symptom:**
Operations fail in specific region but work in others.

**Solution:**
- Some AWS services are region-specific
- Ensure the region is enabled in your AWS account
- Check for region-specific service availability

### Issue: GPUStack Shows "Invalid Credentials"

**Symptom:**
GPUStack UI shows credential validation failed.

**Steps:**
1. Verify Access Key ID starts with `AKIA` or `ASIA`
2. Ensure Secret Key has 40 characters
3. Check region format (should be like `us-east-1`, not `US East`)
4. Verify no extra spaces copied
5. Test with AWS CLI first (see Step 3)

### Issue: InsufficientInstanceCapacity

**Symptom:**
Can create small instances (t2.micro) but GPU instances fail.

**Solution:**
- GPU instances (p3, p4d, g4dn, g5) have limited capacity
- Try different Availability Zones
- Contact AWS Support to request limit increase for GPU instances
- Check [AWS Service Health Dashboard](https://health.aws.amazon.com/)

## Security Best Practices

### 1. Credential Rotation

Rotate credentials every 90 days:
1. Create new Access Key in AWS IAM
2. Update GPUStack with new credentials
3. Test new credentials
4. Deactivate old key
5. Delete old key after 7 days

### 2. Least Privilege

Consider restricting the policy:
- Limit to specific regions using conditions
- Restrict to specific VPCs
- Add time-based restrictions

Example region-restricted policy:
```json
{
    "Condition": {
        "StringEquals": {
            "aws:RequestedRegion": "us-east-1"
        }
    }
}
```

### 3. Monitoring

Enable CloudTrail to monitor API calls:
1. Go to CloudTrail in AWS Console
2. Create trail if not exists
3. Monitor for unexpected EC2 activity
4. Set up alerts for API errors

### 4. Never Commit Credentials

```bash
# Add to .gitignore
echo "aws-credentials.csv" >> .gitignore
echo "*.pem" >> .gitignore
echo ".env" >> .gitignore
```

## Next Steps

After successful validation:

1. ✅ Create a test GPU instance through GPUStack
2. ✅ Verify SSH access works
3. ✅ Test worker registration
4. ✅ Monitor CloudTrail logs
5. ✅ Set up billing alerts

## Support

If you encounter issues:

- **AWS IAM**: https://docs.aws.amazon.com/IAM/latest/UserGuide/
- **GPUStack Docs**: [AWS Provider Integration](./aws-provider.md)
- **Debug Guide**: [AWS Debug & Troubleshooting](./aws-debug-guide.md)

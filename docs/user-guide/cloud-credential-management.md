# Cloud Credential Management

GPUStack supports cloud credential management, allowing secure connections to external cloud providers. Cloud credentials contain provider information, keys, and options required for API access.

## Supported Providers

GPUStack supports the following cloud providers:

- **DigitalOcean** - Provision GPU workers on DigitalOcean Droplets
- **AWS EC2 GPU** - Provision GPU-enabled EC2 instances on AWS ([see AWS provider documentation](../aws-provider.md))

## Create Cloud Credential

### DigitalOcean

1. Go to the `Cloud Credentials` page.
2. Click the `Add Cloud Credential` dropdown and select `DigitalOcean`.
3. Fill in the following information:

   - `Name`: Unique credential name.
   - `Access Token`: The API token generated on the DigitalOcean `Applications & API` page.
   - `Description`: Additional information for the cloud credential.

4. Click the `Save` button.

### AWS EC2 GPU

1. Go to the `Cloud Credentials` page.
2. Click the `Add Cloud Credential` dropdown and select `AWS`.
3. Fill in the following information:

   - `Name`: Unique credential name.
   - `Access Key ID`: Your AWS Access Key ID (e.g., AKIAIOSFODNN7EXAMPLE).
   - `Secret Access Key`: Your AWS Secret Access Key.
   - `Region`: AWS region for instance deployment (default: us-east-1).
   - `VPC ID` (optional): AWS VPC ID for network isolation.
   - `Subnet ID` (optional): Subnet ID for public IP assignment.
   - `Security Group ID` (optional): Security group for instance firewall rules.
   - `Description`: Additional information for the cloud credential.

4. Click the `Save` button.

For detailed AWS provider configuration and advanced options, see the [AWS EC2 GPU Provider documentation](../aws-provider.md).

## Update Cloud Credential

1. Go to the `Cloud Credentials` page.
2. Find the credential you want to edit.
3. Click the `Edit` button.
4. Update the `Name`, `Access Token`, and `Description` as needed.
5. Click the `Save` button.

## Delete Cloud Credential

1. Go to the `Cloud Credentials` page.
2. Find the credential you want to delete.
3. Click the ellipsis button in the operations column, then select `Delete`.
4. Confirm the deletion.

#!/usr/bin/env bash
# Build the SPA with env vars sourced live from CloudFormation, sync to the
# Web bucket, and invalidate CloudFront. Re-run after every SPA change.
#
# Reads outputs directly from CloudFormation (not a local file) so the values
# always match the account/region you're currently authenticated to — single-
# stack `cdk deploy` no longer leaves the SPA pointing at stale infra.
set -euo pipefail

cd "$(dirname "$0")/.."

REGION="${AWS_REGION:-us-east-1}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Deploying to AWS account $ACCOUNT_ID (region $REGION)."
echo

cfn_output() {
  local stack=$1 key=$2 value
  value=$(aws cloudformation describe-stacks \
    --stack-name "$stack" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue | [0]" \
    --output text 2>/dev/null || true)
  if [[ -z "$value" || "$value" == "None" ]]; then
    echo "Missing CloudFormation output ${stack}.${key} in account ${ACCOUNT_ID}/${REGION} — has \`cdk deploy --all\` run here?" >&2
    exit 1
  fi
  printf '%s' "$value"
}

USER_POOL_ID=$(cfn_output HackSci-Auth UserPoolId)
CLIENT_ID=$(cfn_output HackSci-Auth UserPoolClientId)
BUCKET=$(cfn_output HackSci-Web SpaBucketName)
DIST_ID=$(cfn_output HackSci-Web DistributionId)
DIST_DOMAIN=$(cfn_output HackSci-Web DistributionDomainName)

echo "Building SPA with:"
echo "  VITE_COGNITO_USER_POOL_ID=$USER_POOL_ID"
echo "  VITE_COGNITO_CLIENT_ID=$CLIENT_ID"
echo "  (API URL is /api/*, served by CloudFront)"
echo

cd ui

VITE_COGNITO_USER_POOL_ID="$USER_POOL_ID" \
VITE_COGNITO_CLIENT_ID="$CLIENT_ID" \
VITE_COGNITO_REGION="$REGION" \
  npm run build

echo
echo "Syncing dist/ to s3://${BUCKET}/ ..."
aws s3 sync dist/ "s3://$BUCKET/" --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"
aws s3 cp dist/index.html "s3://$BUCKET/index.html" \
  --cache-control "no-cache, max-age=0"

echo
echo "Invalidating CloudFront ${DIST_ID}..."
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

echo
echo "Done. https://$DIST_DOMAIN/"

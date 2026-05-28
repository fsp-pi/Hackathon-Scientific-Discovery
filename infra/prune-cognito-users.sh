#!/usr/bin/env bash
# Delete every user in the HackSci-Auth user pool.
#
# Intended to be run once, post-deploy, after the auth flow switched from
# EMAIL_OTP to password-only. Existing users were created with a throwaway
# client-side password that no one knows, so they're inert — pruning them
# gives a clean slate for the new signup flow.
#
# Safe to re-run: it just lists and deletes whatever's still there.
set -euo pipefail

cd "$(dirname "$0")"

REGION="${AWS_REGION:-us-east-1}"

USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name HackSci-Auth --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue | [0]" \
  --output text)

if [[ -z "$USER_POOL_ID" || "$USER_POOL_ID" == "None" ]]; then
  echo "Could not resolve HackSci-Auth UserPoolId in region ${REGION}." >&2
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Pruning users in user pool ${USER_POOL_ID} (account ${ACCOUNT_ID}/${REGION})."
echo

# list-users paginates at 60 by default; loop until empty.
while :; do
  usernames=$(aws cognito-idp list-users \
    --user-pool-id "$USER_POOL_ID" \
    --region "$REGION" \
    --limit 60 \
    --query "Users[].Username" \
    --output text)

  if [[ -z "$usernames" ]]; then
    echo "No users remaining."
    break
  fi

  for u in $usernames; do
    echo "Deleting $u"
    aws cognito-idp admin-delete-user \
      --user-pool-id "$USER_POOL_ID" \
      --region "$REGION" \
      --username "$u"
  done
done

echo "Done."

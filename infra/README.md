# Agent Society — Infrastructure

AWS CDK (TypeScript) for deploying Agent Society. Single environment, single
region. All stacks share one `App`.

## Stacks

| Stack | Purpose |
|---|---|
| `AgentSociety-Network` | VPC w/ public + private + isolated subnets, single NAT |
| `AgentSociety-Data` | RDS Postgres 16 (`pgvector` enabled in migrations), S3 content bucket |
| `AgentSociety-Auth` | Cognito user pool — email OTP, passwordless |
| `AgentSociety-Api` | ECS Fargate behind ALB, container built from `infra/docker/api/Dockerfile` |
| `AgentSociety-Web` | S3 + CloudFront for the React SPA |

## Prerequisites

- Node 18+ (you're on 22)
- `aws-cli` configured with a profile that has admin-ish permissions
- `cdk` installed globally (you already have it)
- Docker running (CDK builds the API container image locally before pushing)

## First deploy

```bash
cd infra
npm install

# One-time per account/region: provision the CDK bootstrap stack.
npx cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1

# Deploy everything. First run takes ~20 min (RDS is slow to provision).
npm run deploy
```

## Iterating

```bash
npm run diff          # cdk diff against deployed
npm run deploy        # cdk deploy --all
npx cdk deploy AgentSociety-Api    # one stack at a time
```

## Outputs you'll need

After `deploy` completes, grab these from the CFN outputs:

| Output | Used for |
|---|---|
| `AgentSociety-Api.ApiUrl` | Base URL the SPA + Python SDK hit |
| `AgentSociety-Auth.UserPoolId` | Cognito SDK config |
| `AgentSociety-Auth.UserPoolClientId` | Cognito SDK config |
| `AgentSociety-Web.SpaBucketName` | `aws s3 sync` target for the built SPA |
| `AgentSociety-Web.DistributionId` | Invalidation after SPA deploy |
| `AgentSociety-Web.DistributionDomainName` | The public URL |

## Custom domain (deploying to the long-term account)

The CDK app accepts an opt-in `domainName` context flag. When set, `WebStack`
issues an ACM cert (DNS-validated), attaches the apex to CloudFront, and
creates a Route 53 A-alias. When unset, the stack synths exactly as before
(default `*.cloudfront.net` URL). The hosted zone for the domain must live
in the same AWS account that runs `cdk deploy`.

The domain `flagship-hackathon.com` was registered in a different AWS
account from where we deploy. We move the hosted zone (not the registration)
into the deploy account; the registration stays where it is.

### One-time: set up the new account

1. **Create the AWS Organizations sub-account** for the long-term deploy.
   Org root → Accounts → Add an account. Note the new account ID.
2. **Bootstrap CLI creds** via IAM Identity Center (recommended) or an admin
   IAM user. Confirm with `aws sts get-caller-identity` — the account ID
   should match the new sub-account.
3. **Move the hosted zone**:
   - In the **new account**: Route 53 → Hosted zones → Create hosted zone for
     `flagship-hackathon.com` (public). Copy the four `NS` values.
   - In the **domain account**: Route 53 → Registered domains →
     `flagship-hackathon.com` → Edit name servers. Replace all four values
     with the new account's NS records. Save.
   - Wait for propagation (`dig +short NS flagship-hackathon.com` should
     return the new account's nameservers — usually < 30 min).
   - Optional cleanup: delete the empty leftover hosted zone in the domain
     account once propagation is confirmed.
4. **Bootstrap CDK** in the new account:
   ```bash
   npx cdk bootstrap aws://<new-account-id>/us-east-1
   ```

### Deploy with the domain attached

```bash
cd infra
npm run deploy -- -c domainName=flagship-hackathon.com
# or persist it: add "context": { "domainName": "flagship-hackathon.com" } to cdk.context.json
```

First deploy with the domain takes an extra few minutes because ACM has to
validate via DNS. CDK writes the validation CNAMEs into the hosted zone
automatically — no manual record entry needed.

After deploy, the site is reachable at `https://flagship-hackathon.com/`
(SPA) and `https://flagship-hackathon.com/api/*` (API). The CFN output
`HackSci-Web.SiteUrl` prints it.

### Note: this is a fresh environment, not a migration

The new account gets a brand-new Cognito user pool, RDS instance, and S3
buckets. Users in the old account's pool won't carry over, and the old
RDS data doesn't follow either. If anything needs to migrate (registered
users, papers, uploaded content), that's a separate step.

## Bedrock credential vending: one-time IAM setup

The API exposes `POST /api/settings/bedrock-credentials`, which calls
`AssumeRole` on a manually-created role and hands 1-hour STS credentials
to the participant. The role and trust policy are not in CDK because they
must exist before the API stack deploys (the stack consumes the role ARN
via context).

Do this once per AWS account, before the first `cdk deploy`.

### 1. Create the role

```bash
aws iam create-role \
  --role-name HackathonBedrockInvokeRole \
  --max-session-duration 3600 \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::<ACCOUNT_ID>:root" },
      "Action": [
        "sts:AssumeRole",
        "sts:TagSession",
        "sts:SetSourceIdentity"
      ]
    }]
  }'
```

Trust-policy notes:

- The placeholder `<ACCOUNT_ID>:root` lets any principal in the account
  assume the role, gated by IAM policies on those principals. Sufficient
  for a one-day throwaway account. To tighten later, replace `:root` with
  the ECS task role ARN once it exists (look it up with
  `aws iam list-roles | grep HackSci-Api-ServiceTaskDef`) and run
  `aws iam update-assume-role-policy --role-name HackathonBedrockInvokeRole`.
- `sts:TagSession` and `sts:SetSourceIdentity` must be allowed in the
  trust policy, not just the caller's IAM policy. Without them the
  `AssumeRole` call fails even though the action is permitted.

### 2. Attach the Bedrock invoke permission

```bash
aws iam put-role-policy \
  --role-name HackathonBedrockInvokeRole \
  --policy-name BedrockInvokeClaude \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::inference-profile/*",
        "arn:aws:bedrock:*::foundation-model/*"
      ]
    }]
  }'
```

Both ARN types are required: agents call `client.converse(modelId="global.anthropic.claude-...")`, which is a cross-region inference profile that fans out to backing foundation models. Wildcarded across models because participants experiment with model IDs and the existing backend grant is also wildcarded.

### 3. Enable Bedrock model access in the console

In the AWS console, **Bedrock → Model access**, request access to the Claude models from `CLAUDE.md` (`anthropic.claude-opus-4-7`, `anthropic.claude-sonnet-4-6`). IAM allow with console access disabled produces a silent 403 on invoke.

### 4. Set a Bedrock budget alarm

`Billing → Budgets → Create budget`, scope to Bedrock, threshold around `$500` for a one-day event. High enough that legitimate participant traffic doesn't trip it; low enough that a leaked key looping is caught before real money.

### 5. Pass the role ARN into CDK and deploy

```bash
ROLE_ARN=$(aws iam get-role --role-name HackathonBedrockInvokeRole --query 'Role.Arn' --output text)
cd infra
npm run deploy -- -c bedrockVendingRoleArn=$ROLE_ARN
```

Or persist via `cdk.context.json`:

```json
{
  "bedrockVendingRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/HackathonBedrockInvokeRole"
}
```

CDK injects `BEDROCK_VENDING_ROLE_ARN` into the API container and grants the task role `sts:AssumeRole`/`TagSession`/`SetSourceIdentity` scoped to the role ARN. If the context value is omitted, the stack still synths but `POST /api/settings/bedrock-credentials` returns 503.

### Expiry behavior

STS sessions hard-expire at 1 hour. There is no auto-refresh. On expiry the agent's next Bedrock call raises `ExpiredToken`; participants click **Regenerate Bedrock Credentials** in Settings, re-export, and re-run. The agent SDK catches `ExpiredToken` and surfaces a remediation message rather than a raw stack trace. The 1h cap comes from role chaining (ECS task role assuming the vending role) and is not adjustable.

## DB shell access for one-off operations

RDS lives in an isolated subnet, so the only way in from your laptop without setting up a bastion is through the running API task. Use this for ad-hoc data fixes (deleting orphaned preprints, fixing a team row, inspecting state during an incident).

### Prerequisite: ECS execute-command must be enabled on the service

The API stack sets `enableExecuteCommand: true` on the Fargate service, so a normal `cdk deploy AgentSociety-Api` is sufficient. CDK also auto-grants the four `ssmmessages:Create/Open ControlChannel/DataChannel` actions on the task role when this prop is set; no manual IAM patching needed.

If you're operating on an older deployment that predates this prop (or you need to flip it on without a CDK redeploy), patch out of band:

```bash
CLUSTER=$(aws ecs list-clusters --query 'clusterArns[?contains(@, `HackSci-Api`)]|[0]' --output text)
SERVICE=$(aws ecs list-services --cluster $CLUSTER --query 'serviceArns[?contains(@, `HackSci-Api-Service`)]|[0]' --output text)

# Grant ssmmessages:* on the task role (CDK does this automatically when
# enableExecuteCommand is set; only needed when patching out of band).
TASK_DEF=$(aws ecs describe-services --cluster $CLUSTER --services $SERVICE \
  --query 'services[0].taskDefinition' --output text)
TASK_ROLE=$(aws ecs describe-task-definition --task-definition $TASK_DEF \
  --query 'taskDefinition.taskRoleArn' --output text | awk -F/ '{print $NF}')

aws iam put-role-policy \
  --role-name $TASK_ROLE \
  --policy-name SSMMessagesForExec \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ],
      "Resource": "*"
    }]
  }'

aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --enable-execute-command \
  --force-new-deployment

aws ecs wait services-stable --cluster $CLUSTER --services $SERVICE
```

If you see "The execute command failed because execute command was not enabled when the task was run", the running task predates the flag flip. Wait for the new deployment to cut over, or `--force-new-deployment` again.

### Open a shell into a running task

```bash
TASK=$(aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE --query 'taskArns[0]' --output text)
CONTAINER=$(aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK --query 'tasks[0].containers[0].name' --output text)

aws ecs execute-command \
  --cluster $CLUSTER \
  --task $TASK \
  --container $CONTAINER \
  --interactive \
  --command "/bin/sh"
```

Inside the container, `DB_HOST`, `DB_USERNAME`, `DB_PASSWORD`, and `DB_NAME` are populated from the task's env + secrets. The image does not include `psql`, so use Python:

```bash
python -c "
import psycopg, os
conn = psycopg.connect(
    host=os.environ['DB_HOST'],
    user=os.environ['DB_USERNAME'],
    password=os.environ['DB_PASSWORD'],
    dbname=os.environ['DB_NAME'],
)
cur = conn.cursor()
cur.execute('SELECT count(*) FROM papers')
print(cur.fetchone())
"
```

### Recipe: delete a team's preprints

A team that hits `PREPRINTS_PER_TEAM_PER_ROUND_CAP` (1000 preprints in the current round) needs that round's preprints purged. The API does not expose a delete endpoint, so do it directly. Always SELECT first to confirm scope, then DELETE. The cap is **per round**, so always scope by `round` — operating on all of a team's preprints would also delete preprints from prior rounds, which are still citeable on Browse.

```python
# inside the container shell
import psycopg, os
conn = psycopg.connect(
    host=os.environ['DB_HOST'],
    user=os.environ['DB_USERNAME'],
    password=os.environ['DB_PASSWORD'],
    dbname=os.environ['DB_NAME'],
)
cur = conn.cursor()

team = '<team-slug>'
round_n = int(os.environ.get('HACKATHON_CURRENT_ROUND', '1'))

# Confirm scope
cur.execute(
    "SELECT count(*) FROM papers "
    "WHERE team_id = %s AND kind = 'preprint' AND round = %s",
    (team, round_n),
)
print('preprints to delete:', cur.fetchone()[0])

# Delete (preprints only in this round, never touch submissions or other rounds)
cur.execute(
    "DELETE FROM papers "
    "WHERE team_id = %s AND kind = 'preprint' AND round = %s",
    (team, round_n),
)
print('deleted:', cur.rowcount)
conn.commit()
```

To keep the most recent N from the current round and delete the rest:

```python
cur.execute(
    """
    DELETE FROM papers
    WHERE id IN (
      SELECT id FROM papers
      WHERE team_id = %s AND kind = 'preprint' AND round = %s
      ORDER BY created_at ASC
      LIMIT %s
    )
    """,
    (team, round_n, 900),
)
```

### Turning execute-command off

The CDK default is on, so adopt this only if you want the surface gone outside of incidents. Flip `enableExecuteCommand` to `false` in `infra/lib/api-stack.ts` and redeploy, or patch out of band:

```bash
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --no-enable-execute-command \
  --force-new-deployment
```

## Notes

- **Cost**: ~$45-60/mo idle (NAT ~$32, RDS t4g.micro ~$13, Fargate 0.5 vCPU ~$10, the rest is rounding). Most of that is the NAT gateway — we can replace it with VPC endpoints later if cost matters.
- **TLS**: With `domainName` set, CloudFront terminates TLS for the custom domain via an ACM cert. The ALB is still HTTP-only — CloudFront talks to it over HTTP inside AWS, viewers see HTTPS end-to-end. Without `domainName`, the SPA is served from the default `*.cloudfront.net` cert.
- **No `prod`**: there is one environment. Tag stacks with `ENV=prod` if/when that changes.
- **Destroying**: `npm run destroy` will tear down everything except the S3 content bucket (RETAIN policy) and the Cognito user pool (RETAIN). Both must be deleted manually if you really want a clean slate.

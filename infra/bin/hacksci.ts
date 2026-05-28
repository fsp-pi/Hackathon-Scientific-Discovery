#!/usr/bin/env node
import "source-map-support/register";
import { App } from "aws-cdk-lib";
import { NetworkStack } from "../lib/network-stack";
import { DataStack } from "../lib/data-stack";
import { AuthStack } from "../lib/auth-stack";
import { ApiStack } from "../lib/api-stack";
import { WebStack } from "../lib/web-stack";

const app = new App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
};

// Custom domain. Defaulted by account so prod synths don't need a magic flag —
// without this, `cdk deploy` against prod would treat the WebStack as
// domain-less and CloudFormation would diff "destroy the prod TLS cert + apex
// alias", which is exactly the footgun we hit before locking it in here.
// Dev/sandbox accounts still get no domain. Override with
// `cdk deploy -c domainName=<other-domain>`.
const PROD_ACCOUNT = "289835834978";
const PROD_DOMAIN = "flagship-hackathon.com";
const domainName =
  (app.node.tryGetContext("domainName") as string | undefined) ||
  (env.account === PROD_ACCOUNT ? PROD_DOMAIN : undefined);

// Bedrock credential vending. Created manually in the deploy account before
// first deploy (see infra/README.md). Pass with
// `cdk deploy -c bedrockVendingRoleArn=arn:aws:iam::...:role/HackathonBedrockInvokeRole`.
const bedrockVendingRoleArn = app.node.tryGetContext("bedrockVendingRoleArn") as
  | string
  | undefined;

const network = new NetworkStack(app, "HackSci-Network", { env });

const data = new DataStack(app, "HackSci-Data", {
  env,
  vpc: network.vpc,
});

const auth = new AuthStack(app, "HackSci-Auth", { env });

const api = new ApiStack(app, "HackSci-Api", {
  env,
  vpc: network.vpc,
  db: data.db,
  dbSecret: data.dbSecret,
  dbSecurityGroup: data.dbSecurityGroup,
  userPool: auth.userPool,
  userPoolClient: auth.userPoolClient,
  bedrockVendingRoleArn,
});

new WebStack(app, "HackSci-Web", {
  env,
  apiLoadBalancer: api.service.loadBalancer,
  domainName,
});

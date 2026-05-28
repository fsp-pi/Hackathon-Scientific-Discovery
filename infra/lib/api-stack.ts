import * as path from "path";
import {
  CfnOutput,
  Duration,
  Stack,
  StackProps,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import {
  CfnSecurityGroupIngress,
  SubnetType,
  Vpc,
} from "aws-cdk-lib/aws-ec2";
import { Platform } from "aws-cdk-lib/aws-ecr-assets";
import {
  Cluster,
  ContainerImage,
  CpuArchitecture,
  LogDrivers,
  OperatingSystemFamily,
} from "aws-cdk-lib/aws-ecs";
import { ApplicationLoadBalancedFargateService } from "aws-cdk-lib/aws-ecs-patterns";
import { ApplicationProtocol } from "aws-cdk-lib/aws-elasticloadbalancingv2";
import { UserPool, UserPoolClient } from "aws-cdk-lib/aws-cognito";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import { DatabaseInstance } from "aws-cdk-lib/aws-rds";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";
import { RetentionDays } from "aws-cdk-lib/aws-logs";
import { SecurityGroup } from "aws-cdk-lib/aws-ec2";
import { Secret as EcsSecret } from "aws-cdk-lib/aws-ecs";

interface ApiStackProps extends StackProps {
  vpc: Vpc;
  db: DatabaseInstance;
  dbSecret: Secret;
  dbSecurityGroup: SecurityGroup;
  userPool: UserPool;
  userPoolClient: UserPoolClient;
  bedrockVendingRoleArn?: string;
}

export class ApiStack extends Stack {
  public readonly service: ApplicationLoadBalancedFargateService;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const cluster = new Cluster(this, "Cluster", {
      vpc: props.vpc,
      containerInsights: true,
    });

    // Build context is the repo root so the Dockerfile can COPY from
    // pyproject.toml and hackathon_science/. The path is relative to this file.
    const repoRoot = path.resolve(__dirname, "..", "..");
    const image = ContainerImage.fromAsset(repoRoot, {
      file: "infra/docker/api/Dockerfile",
      platform: Platform.LINUX_ARM64,
    });

    this.service = new ApplicationLoadBalancedFargateService(this, "Service", {
      cluster,
      cpu: 512,
      memoryLimitMiB: 1024,
      desiredCount: 1,
      publicLoadBalancer: true,
      protocol: ApplicationProtocol.HTTP,
      assignPublicIp: false,
      enableExecuteCommand: true,
      taskSubnets: { subnetType: SubnetType.PRIVATE_WITH_EGRESS },
      runtimePlatform: {
        cpuArchitecture: CpuArchitecture.ARM64,
        operatingSystemFamily: OperatingSystemFamily.LINUX,
      },
      taskImageOptions: {
        image,
        containerPort: 8000,
        environment: {
          AWS_REGION: this.region,
          DB_HOST: props.db.dbInstanceEndpointAddress,
          DB_PORT: props.db.dbInstanceEndpointPort,
          DB_NAME: "hacksci",
          COGNITO_USER_POOL_ID: props.userPool.userPoolId,
          COGNITO_CLIENT_ID: props.userPoolClient.userPoolClientId,
          ...(props.bedrockVendingRoleArn
            ? { BEDROCK_VENDING_ROLE_ARN: props.bedrockVendingRoleArn }
            : {}),
        },
        secrets: {
          DB_USERNAME: EcsSecret.fromSecretsManager(props.dbSecret, "username"),
          DB_PASSWORD: EcsSecret.fromSecretsManager(props.dbSecret, "password"),
        },
        logDriver: LogDrivers.awsLogs({
          streamPrefix: "api",
          logRetention: RetentionDays.ONE_MONTH,
        }),
      },
    });

    this.service.targetGroup.configureHealthCheck({
      path: "/health",
      healthyHttpCodes: "200",
      interval: Duration.seconds(30),
      timeout: Duration.seconds(5),
    });

    new CfnSecurityGroupIngress(this, "DbIngressFromApi", {
      groupId: props.dbSecurityGroup.securityGroupId,
      sourceSecurityGroupId:
        this.service.service.connections.securityGroups[0].securityGroupId,
      ipProtocol: "tcp",
      fromPort: 5432,
      toPort: 5432,
      description: "API tasks to Postgres",
    });

    // Bedrock InvokeModel for Claude — agents call this via the CLI, but the
    // API also calls it for server-side flows like activity summarisation
    // (later). Granted broadly to *foundation-model/* so individual model IDs
    // don't require redeploys when the team switches between Claude SKUs.
    this.service.taskDefinition.taskRole.addToPrincipalPolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources: ["arn:aws:bedrock:*::foundation-model/*"],
      }),
    );

    // Credential vending: let the task role AssumeRole on the manually-created
    // HackathonBedrockInvokeRole (see infra/README.md). Resulting STS sessions
    // are handed to participants via POST /api/settings/bedrock-credentials.
    if (props.bedrockVendingRoleArn) {
      this.service.taskDefinition.taskRole.addToPrincipalPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ["sts:AssumeRole", "sts:TagSession", "sts:SetSourceIdentity"],
          resources: [props.bedrockVendingRoleArn],
        }),
      );
    }

    new CfnOutput(this, "ApiUrl", {
      value: `http://${this.service.loadBalancer.loadBalancerDnsName}`,
    });
  }
}

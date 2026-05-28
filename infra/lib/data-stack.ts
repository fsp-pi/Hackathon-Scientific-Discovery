import {
  Duration,
  RemovalPolicy,
  Stack,
  StackProps,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import {
  InstanceClass,
  InstanceSize,
  InstanceType,
  SecurityGroup,
  SubnetType,
  Vpc,
} from "aws-cdk-lib/aws-ec2";
import {
  Credentials,
  DatabaseInstance,
  DatabaseInstanceEngine,
  PostgresEngineVersion,
  StorageType,
} from "aws-cdk-lib/aws-rds";
import { Secret } from "aws-cdk-lib/aws-secretsmanager";

interface DataStackProps extends StackProps {
  vpc: Vpc;
}

export class DataStack extends Stack {
  public readonly db: DatabaseInstance;
  public readonly dbSecret: Secret;
  public readonly dbSecurityGroup: SecurityGroup;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    this.dbSecurityGroup = new SecurityGroup(this, "DbSecurityGroup", {
      vpc: props.vpc,
      description: "Postgres ingress - restricted to API security group",
      allowAllOutbound: false,
    });

    this.db = new DatabaseInstance(this, "Postgres", {
      engine: DatabaseInstanceEngine.postgres({
        version: PostgresEngineVersion.VER_16_13,
      }),
      vpc: props.vpc,
      vpcSubnets: { subnetType: SubnetType.PRIVATE_ISOLATED },
      instanceType: InstanceType.of(InstanceClass.T4G, InstanceSize.MICRO),
      securityGroups: [this.dbSecurityGroup],
      credentials: Credentials.fromGeneratedSecret("hacksci", {
        secretName: "hacksci/db",
      }),
      databaseName: "hacksci",
      allocatedStorage: 20,
      maxAllocatedStorage: 100,
      storageType: StorageType.GP3,
      multiAz: false,
      backupRetention: Duration.days(7),
      deletionProtection: false,
      removalPolicy: RemovalPolicy.SNAPSHOT,
      publiclyAccessible: false,
    });

    this.dbSecret = this.db.secret as Secret;
  }
}

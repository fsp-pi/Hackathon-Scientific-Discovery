import {
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  StackProps,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import {
  AccountRecovery,
  ClientAttributes,
  FeaturePlan,
  StringAttribute,
  UserPool,
  UserPoolClient,
} from "aws-cdk-lib/aws-cognito";
import { Code, Function as LambdaFunction, Runtime } from "aws-cdk-lib/aws-lambda";

export class AuthStack extends Stack {
  public readonly userPool: UserPool;
  public readonly userPoolClient: UserPoolClient;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Auto-confirm every sign-up and mark email as verified, so Cognito never
    // sends a verification email. Combined with the password-only sign-in
    // factor below, the user pool has zero email-sending paths — bypasses the
    // 50/day default-sender cap entirely.
    const preSignupFn = new LambdaFunction(this, "PreSignup", {
      runtime: Runtime.NODEJS_20_X,
      handler: "index.handler",
      code: Code.fromInline(
        "exports.handler = async (event) => {\n" +
        "  event.response.autoConfirmUser = true;\n" +
        "  event.response.autoVerifyEmail = true;\n" +
        "  return event;\n" +
        "};\n",
      ),
    });

    this.userPool = new UserPool(this, "UserPool", {
      userPoolName: "hacksci",
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      // Suppress CDK's implicit AutoVerifiedAttributes default (derived from
      // signInAliases.email). The Pre-Signup Lambda already sets the email as
      // verified, so this attribute would only matter for paths the Lambda
      // doesn't cover (e.g. admin-create-user), and we don't use those.
      autoVerify: { email: false },
      standardAttributes: {
        email: { required: true, mutable: false },
      },
      customAttributes: {
        // Each user belongs to one team — set on sign-up, never edited by the
        // user themselves. The team name is what's shown on the Activity page.
        team_name: new StringAttribute({ minLen: 1, maxLen: 64, mutable: false }),
      },
      featurePlan: FeaturePlan.ESSENTIALS,
      // Password-only sign-in. EMAIL_OTP is gone so no per-sign-in email goes
      // out; combined with the PreSignup auto-confirm trigger, the pool sends
      // no emails at all.
      signInPolicy: {
        allowedFirstAuthFactors: {
          password: true,
        },
      },
      // No password reset path — temp event environment. If a user gets locked
      // out, run `aws cognito-idp admin-set-user-password` manually.
      accountRecovery: AccountRecovery.NONE,
      lambdaTriggers: {
        preSignUp: preSignupFn,
      },
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // CDK's defaults for the SPA client don't include custom attributes, which
    // makes signUp() silently fail when it tries to set custom:team_name. We
    // list the custom attribute explicitly in both read and write. email_verified
    // is read-only (Cognito-controlled) so it appears only in readAttributes.
    const readAttrs = new ClientAttributes()
      .withStandardAttributes({ email: true, emailVerified: true })
      .withCustomAttributes("team_name");
    const writeAttrs = new ClientAttributes()
      .withStandardAttributes({ email: true })
      .withCustomAttributes("team_name");

    this.userPoolClient = this.userPool.addClient("SpaClient", {
      userPoolClientName: "hacksci-spa",
      generateSecret: false,
      authFlows: {
        // userSrp is the password sign-in flow used by the SPA. `user` (the
        // choice-based USER_AUTH flow) is left enabled in case we add factors
        // back later, but the SPA only uses userSrp today.
        user: true,
        userSrp: true,
      },
      // Disabled so the SPA can fall through from "sign in" to "sign up" when
      // it sees UserNotFoundException. With this enabled, Cognito masks the
      // error as a generic NotAuthorizedException and the UX breaks.
      preventUserExistenceErrors: false,
      readAttributes: readAttrs,
      writeAttributes: writeAttrs,
      refreshTokenValidity: Duration.days(30),
      accessTokenValidity: Duration.hours(1),
      idTokenValidity: Duration.hours(1),
    });

    new CfnOutput(this, "UserPoolId", { value: this.userPool.userPoolId });
    new CfnOutput(this, "UserPoolClientId", { value: this.userPoolClient.userPoolClientId });
  }
}

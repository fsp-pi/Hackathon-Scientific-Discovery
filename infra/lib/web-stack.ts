import {
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  StackProps,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import {
  Certificate,
  CertificateValidation,
} from "aws-cdk-lib/aws-certificatemanager";
import {
  AllowedMethods,
  CachePolicy,
  Distribution,
  OriginProtocolPolicy,
  OriginRequestPolicy,
  PriceClass,
  ViewerProtocolPolicy,
} from "aws-cdk-lib/aws-cloudfront";
import { LoadBalancerV2Origin, S3BucketOrigin } from "aws-cdk-lib/aws-cloudfront-origins";
import { ApplicationLoadBalancer } from "aws-cdk-lib/aws-elasticloadbalancingv2";
import { ARecord, HostedZone, RecordTarget } from "aws-cdk-lib/aws-route53";
import { CloudFrontTarget } from "aws-cdk-lib/aws-route53-targets";
import {
  BlockPublicAccess,
  Bucket,
  BucketEncryption,
  ObjectOwnership,
} from "aws-cdk-lib/aws-s3";

interface WebStackProps extends StackProps {
  apiLoadBalancer: ApplicationLoadBalancer;
  // Apex domain to attach to the CloudFront distribution. When undefined,
  // the distribution is reachable only at its default *.cloudfront.net name.
  // The hosted zone for this domain must live in the same AWS account.
  domainName?: string;
}

export class WebStack extends Stack {
  public readonly bucket: Bucket;
  public readonly distribution: Distribution;

  constructor(scope: Construct, id: string, props: WebStackProps) {
    super(scope, id, props);

    this.bucket = new Bucket(this, "SpaBucket", {
      versioned: false,
      encryption: BucketEncryption.S3_MANAGED,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      objectOwnership: ObjectOwnership.BUCKET_OWNER_ENFORCED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Optional custom-domain wiring. The stack is already in us-east-1, so
    // the ACM cert can live in this stack directly (CloudFront only accepts
    // us-east-1 certs). DNS validation writes CNAMEs into the hosted zone
    // automatically — the zone must already exist in this account.
    let certificate: Certificate | undefined;
    let hostedZone: HostedZone | undefined;
    if (props.domainName) {
      hostedZone = HostedZone.fromLookup(this, "HostedZone", {
        domainName: props.domainName,
      }) as HostedZone;
      certificate = new Certificate(this, "Certificate", {
        domainName: props.domainName,
        validation: CertificateValidation.fromDns(hostedZone),
      });
    }

    // CloudFront fronts both the SPA (S3 origin) and the API (ALB origin)
    // on the same domain. This avoids browser mixed-content errors (the
    // ALB is HTTP-only until we have a domain to issue an ACM cert for)
    // and removes the need for CORS preflights.
    this.distribution = new Distribution(this, "Distribution", {
      domainNames: props.domainName ? [props.domainName] : undefined,
      certificate,
      defaultBehavior: {
        origin: S3BucketOrigin.withOriginAccessControl(this.bucket),
        viewerProtocolPolicy: ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachePolicy: CachePolicy.CACHING_OPTIMIZED,
        compress: true,
      },
      additionalBehaviors: {
        "/api/*": {
          // CloudFront talks to the ALB over HTTP. CloudFront-to-viewer is
          // still HTTPS, so the SPA stays mixed-content-safe.
          origin: new LoadBalancerV2Origin(props.apiLoadBalancer, {
            protocolPolicy: OriginProtocolPolicy.HTTP_ONLY,
            httpPort: 80,
            readTimeout: Duration.seconds(60),
            keepaliveTimeout: Duration.seconds(60),
          }),
          viewerProtocolPolicy: ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: AllowedMethods.ALLOW_ALL,
          // Pass Authorization through (CachingDisabled does NOT forward
          // it by default), and don't cache — every response is a query
          // result keyed on the auth token.
          cachePolicy: CachePolicy.CACHING_DISABLED,
          originRequestPolicy: OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          compress: true,
        },
      },
      defaultRootObject: "index.html",
      // SPA fallback: S3 returns 403 for missing objects under OAC, 404 for
      // missing prefixes. Both should serve index.html so React Router can
      // resolve client-side routes. /api/* responses bypass this because
      // they don't traverse the default behavior.
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: Duration.seconds(10),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: Duration.seconds(10),
        },
      ],
      priceClass: PriceClass.PRICE_CLASS_100,
    });

    // Apex A-alias to CloudFront. ARecord with an alias target works for the
    // apex (CNAME would not, since CNAMEs aren't allowed at the zone apex).
    if (props.domainName && hostedZone) {
      new ARecord(this, "ApexAlias", {
        zone: hostedZone,
        recordName: props.domainName,
        target: RecordTarget.fromAlias(new CloudFrontTarget(this.distribution)),
      });
    }

    new CfnOutput(this, "SpaBucketName", { value: this.bucket.bucketName });
    new CfnOutput(this, "DistributionDomainName", {
      value: this.distribution.distributionDomainName,
    });
    new CfnOutput(this, "DistributionId", {
      value: this.distribution.distributionId,
    });
    if (props.domainName) {
      new CfnOutput(this, "SiteUrl", {
        value: `https://${props.domainName}`,
      });
    }
  }
}

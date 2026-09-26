import * as path from "path";
import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigw from "aws-cdk-lib/aws-apigateway";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

/**
 * Infrastructure for the Travel Pricing & Growth Advisor.
 *
 * Layout:
 *   S3 (seed data) -> Lambda (pricing / growth) <- API Gateway (REST) -> client
 *   Lambdas write cached results to a DynamoDB table.
 *
 * Validated with `cdk synth`; no AWS credentials or live deploy required.
 */
export class TravelAdvisorStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const repoRoot = path.join(__dirname, "..", "..");
    const backendSrc = path.join(repoRoot, "backend", "src");
    const dataDir = path.join(repoRoot, "data");

    // --- Seed data bucket ------------------------------------------------- //
    const dataBucket = new s3.Bucket(this, "SeedDataBucket", {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    new s3deploy.BucketDeployment(this, "DeploySeedData", {
      sources: [s3deploy.Source.asset(dataDir)],
      destinationBucket: dataBucket,
      destinationKeyPrefix: "data",
    });

    // --- Results cache table --------------------------------------------- //
    const resultsTable = new dynamodb.Table(this, "ResultsTable", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // --- Lambda functions (bundle the Python core) ----------------------- //
    const commonEnv = {
      DATA_BUCKET: dataBucket.bucketName,
      RESULTS_TABLE: resultsTable.tableName,
    };

    const codeAsset = lambda.Code.fromAsset(backendSrc);

    const pricingFn = new lambda.Function(this, "PricingLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "travel_advisor.api.lambda_price",
      code: codeAsset,
      memorySize: 256,
      timeout: cdk.Duration.seconds(15),
      environment: commonEnv,
    });

    const growthFn = new lambda.Function(this, "GrowthLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "travel_advisor.api.lambda_growth",
      code: codeAsset,
      memorySize: 256,
      timeout: cdk.Duration.seconds(15),
      environment: commonEnv,
    });

    const storylineFn = new lambda.Function(this, "StorylineLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "travel_advisor.api.lambda_storyline",
      code: codeAsset,
      memorySize: 256,
      timeout: cdk.Duration.seconds(15),
      environment: commonEnv,
    });

    // Least-privilege grants.
    for (const fn of [pricingFn, growthFn, storylineFn]) {
      dataBucket.grantRead(fn);
      resultsTable.grantReadWriteData(fn);
    }

    // --- REST API -------------------------------------------------------- //
    const api = new apigw.RestApi(this, "TravelAdvisorApi", {
      restApiName: "travel-advisor",
      description: "Pricing, growth, and storyline API",
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS,
        allowMethods: apigw.Cors.ALL_METHODS,
      },
      deployOptions: { stageName: "prod" },
    });

    api.root
      .addResource("price")
      .addMethod("GET", new apigw.LambdaIntegration(pricingFn));
    api.root
      .addResource("growth")
      .addMethod("GET", new apigw.LambdaIntegration(growthFn));
    api.root
      .addResource("storyline")
      .addMethod("GET", new apigw.LambdaIntegration(storylineFn));

    // --- Outputs --------------------------------------------------------- //
    new cdk.CfnOutput(this, "ApiUrl", { value: api.url });
    new cdk.CfnOutput(this, "SeedDataBucketName", { value: dataBucket.bucketName });
    new cdk.CfnOutput(this, "ResultsTableName", { value: resultsTable.tableName });
  }
}

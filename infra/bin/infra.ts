#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { TravelAdvisorStack } from "../lib/travel-advisor-stack";

const app = new cdk.App();

new TravelAdvisorStack(app, "TravelAdvisorStack", {
  description:
    "Event-driven dynamic pricing and international growth advisor for the travel vertical",
  // env is intentionally unset so `cdk synth` runs without AWS credentials.
});

app.synth();

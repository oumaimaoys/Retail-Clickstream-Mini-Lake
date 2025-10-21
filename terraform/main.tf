terraform {
  required_providers { aws = { source = "hashicorp/aws", version = "~> 5.0" } }
}
provider "aws" { region = var.region }

variable "bucket" {}
variable "region" { default = "eu-west-1" }

resource "aws_s3_bucket" "clicks" {
  bucket = var.bucket
  force_destroy = true
}

resource "aws_iam_role" "redshift_s3_read" {
  name = "RedshiftS3Read"
  assume_role_policy = jsonencode({
    Version="2012-10-17",
    Statement=[{
      Effect="Allow",
      Principal={ Service="redshift.amazonaws.com" },
      Action="sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rs_s3" {
  role       = aws_iam_role.redshift_s3_read.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}

/* For classic Redshift (simplified; you must add subnet group + SGs)
resource "aws_redshift_cluster" "this" {
  cluster_identifier = "rcml-cluster"
  node_type          = "dc2.large"
  number_of_nodes    = 1
  database_name      = "dev"
  master_username    = "awsuser"
  master_password    = "SuperSecret123"
  iam_roles          = [aws_iam_role.redshift_s3_read.arn]
  publicly_accessible = true
}
*/
output "role_arn" { value = aws_iam_role.redshift_s3_read.arn }

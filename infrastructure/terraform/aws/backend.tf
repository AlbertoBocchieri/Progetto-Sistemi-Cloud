terraform {
  backend "s3" {
    bucket       = "parcheggia-dev-terraform-state-053524633862-eu-south-1"
    key          = "terraform/aws/terraform.tfstate"
    region       = "eu-south-1"
    encrypt      = true
    use_lockfile = true
  }
}

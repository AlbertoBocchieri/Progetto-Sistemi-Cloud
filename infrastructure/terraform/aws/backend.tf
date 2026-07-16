terraform {
  backend "s3" {
    key          = "terraform/aws/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

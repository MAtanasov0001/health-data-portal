# Заготовка (режим B). Без реални ресурси — те се добавят при започване на инфраструктурата.
# Фиксираме изискванията към версиите за възпроизводимост (защита срещу неочаквани промени).

terraform {
  required_version = ">= 1.7.0"
}

locals {
  # Общи етикети за всички бъдещи ресурси.
  common_tags = {
    project     = "open-health-data-portal"
    environment = var.environment
    managed_by  = "terraform"
  }
}

output "environment" {
  value = var.environment
}

output "public_base_url" {
  value = var.public_base_url
}

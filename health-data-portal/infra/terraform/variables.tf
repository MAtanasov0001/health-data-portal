variable "environment" {
  description = "Име на средата (напр. staging, production)."
  type        = string
}

variable "region" {
  description = "Регион/зона на облака (ДХЧО или съвместим)."
  type        = string
  default     = "bg-sofia-1"
}

variable "public_base_url" {
  description = "Публичен базов адрес на портала."
  type        = string
}

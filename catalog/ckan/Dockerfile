# CKAN — каталожно ядро (вариант А) + ckanext-dcat за DCAT-AP сериализация и
# CKAN-съвместими крайни точки за харвестване (data.egov.bg / data.europa.eu).
#
# Режим B. Локална/демо среда — НЕ за продукция. Продукционната инсталация на
# CKAN (тайни, идентичност, мащабиране) е режим C и е извън тази фаза.
FROM ckan/ckan-base:2.10

# Фиксирана версия — възпроизводимост и защита срещу slopsquatting (концепция 15).
ARG CKANEXT_DCAT_VERSION=1.7.0

USER root
RUN /usr/lib/ckan/venv/bin/pip install --no-cache-dir \
        "ckanext-dcat==${CKANEXT_DCAT_VERSION}"

# Първоначална подготовка (db init, sysadmin, API токен) — базовият entrypoint
# изпълнява всички изпълними скриптове в /docker-entrypoint.d/ преди старта.
COPY docker-entrypoint.d/10_bootstrap.sh /docker-entrypoint.d/10_bootstrap.sh
RUN chmod +x /docker-entrypoint.d/10_bootstrap.sh

# CKAN върви като непривилегирован потребител (образът дефинира 'ckan', uid 92).
USER ckan

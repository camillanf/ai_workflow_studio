# Contribuir a AI Workflow Studio

Gracias por interesarse en contribuir. Este módulo se desarrolla para **Odoo 19 Community**.

## Cómo contribuir

1. Bifique el repositorio y cree una rama desde `19.0`.
2. Realice sus cambios siguiendo las convenciones del módulo (PEP8, ruff, vistas `<list>`, expresiones `invisible/readonly/required` en lugar de `attrs`).
3. Añada o actualice las pruebas en `tests/` (`TransactionCase`, tag `ai_workflow_studio`).
4. Actualice la documentación en `docs/` si el cambio afecta arquitectura o diseño.
5. Envíe un pull request describiendo el cambio y las pruebas realizadas.

## Estándares

- Python: PEP8 / ruff (configuración en la raíz del repositorio).
- XML Odoo 19: vistas `<list>` (no `<tree>`), expresiones `invisible/readonly/required`.
- i18n: cadenas traducibles; regenerar `i18n/ai_workflow_studio.pot` tras cambios de strings.
- No se aceptan dependencias de pago, Enterprise ni librerías no justificadas.

## Pruebas

```bash
./odoo-bin -c odoo.conf -d odoodb -u ai_workflow_studio --test-tags /ai_workflow_studio --stop-after-init
```

Debe terminar con `0 failed, 0 error(s)`.

## Licencia

LGPL-3. Las contribuciones se aceptan bajo la misma licencia.

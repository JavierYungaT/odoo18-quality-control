# Backlog (Scrum)

Producto: control de calidad para Odoo 18 Community. Sprints de una semana.

## Sprint 1: Base del módulo

| ID | Historia de usuario | Criterios de aceptación | Estado |
|---|---|---|---|
| QC-1 | Como **jefe de calidad**, quiero definir puntos de control por tipo de operación y producto, para decidir qué se inspecciona. | Punto con operaciones, productos o categorías; tipo aprobado/rechazado o medición; tolerancias validadas. | Hecho |
| QC-2 | Como **administrador**, quiero grupos Usuario y Administrador de calidad, para separar quién inspecciona de quién configura. | Permisos por grupo; reglas multi-compañía. | Hecho |

## Sprint 2: Inspecciones en el flujo de inventario

| ID | Historia de usuario | Criterios de aceptación | Estado |
|---|---|---|---|
| QC-3 | Como **bodeguero**, quiero que las inspecciones se creen solas al confirmar una recepción, para no olvidarlas. | También funciona con recepciones creadas desde una orden de compra; sin duplicados. | Hecho |
| QC-4 | Como **jefe de calidad**, quiero que no se pueda validar una recepción con inspecciones pendientes o fallidas sin alerta. | `button_validate` muestra un error claro con las referencias. | Hecho |
| QC-5 | Como **inspector**, quiero registrar mediciones y que el resultado se calcule según la tolerancia. | Dentro de la tolerancia aprueba y fuera rechaza; no se puede forzar un resultado contrario. | Hecho |

## Sprint 3: Manufactura, compras y ventas

| ID | Historia de usuario | Criterios de aceptación | Estado |
|---|---|---|---|
| QC-6 | Como **jefe de planta**, quiero inspeccionar el producto terminado antes de cerrar la orden de producción. | Inspección creada al confirmar; `button_mark_done` bloqueado. | Hecho |
| QC-7 | Como **comprador**, quiero ver el puntaje de calidad del proveedor y una advertencia si está bajo el mínimo. | Puntaje en el contacto y en la orden de compra; mínimo configurable en Ajustes. | Hecho |
| QC-8 | Como **vendedor**, quiero registrar un reclamo de cliente desde el pedido de venta. | Botón en el pedido confirmado; alerta prellenada; botón inteligente con el conteo. | Hecho |

## Sprint 4: No conformidades, reportes y dashboard

| ID | Historia de usuario | Criterios de aceptación | Estado |
|---|---|---|---|
| QC-9 | Como **jefe de calidad**, quiero gestionar alertas en kanban con responsable, fecha límite y costo. | Etapas configurables; costo = cantidad × costo del producto; cierre solo con causa raíz y acción correctiva. | Hecho |
| QC-10 | Como **responsable**, quiero un recordatorio cuando una alerta vence. | Cron diario que crea una actividad sin duplicarla. | Hecho |
| QC-11 | Como **cliente**, quiero un certificado de calidad en PDF de mi entrega. | Reporte QWeb PDF en el menú Imprimir de la transferencia. | Hecho |
| QC-12 | Como **gerente**, quiero un tablero con indicadores y un análisis por proveedor y mes. | Dashboard OWL; vista SQL con pivot y gráfico; reporte HTML de proveedor. | Hecho |

## Pendiente (siguientes sprints)

- QC-13: Inspección por muestreo (AQL) según la cantidad recibida.
- QC-14: Fotos de evidencia desde el móvil.
- QC-15: Nota de crédito al proveedor desde una alerta (Contabilidad).
- QC-16: Inspecciones por orden de trabajo (Manufactura con rutas).

# Appian CI/CD Wrapper Template

Repositorio plantilla para orquestar despliegues automatizados de aplicaciones **Appian** utilizando las acciones del **Appian CI/CD Core**.  
Define la estructura mínima y las convenciones necesarias para que cada aplicación integre GitHub Actions con la plataforma Appian.

> ℹ️ El detalle completo de configuración y uso se documenta en el **Manual de Usuario** incluido en este repositorio (`Manual_de_Usuario_CICD_Appian__GitHub.pdf`). Este README resume los conceptos principales.

---

## 🧭 Propósito

El *wrapper* actúa como intermediario entre las aplicaciones Appian y el Core CI/CD.  
Centraliza las configuraciones, credenciales y workflows necesarios para ejecutar despliegues controlados entre entornos (Dev → QA → Prod).

---

## ⚙️ Funcionalidad principal

- Orquestación de exportación, inspección y promoción de aplicaciones Appian.  
- Integración directa con las acciones del Core (no se replica lógica).  
- Control de credenciales, variables y overrides por entorno.  
- Validaciones previas y gates manuales definidos mediante Environments.  
- Trazabilidad y versionado de cada ejecución/artefacto.

---

## 🧩 Estructura del repositorio

- `.github/workflows/` — Workflows `deploy-app.yml` y `deploy-package.yml` (wrappers).  
- `.github/scripts/` — utilidades complementarias (ej. `create_release.py`).  
- `appian-artifacts/` — exportaciones y metadatos versionados automáticamente.  
- `Manual_de_Usuario_CICD_Appian__GitHub.pdf` — guía oficial con el paso a paso.  
- Otros directorios (`provisioning/`, etc.) pueden contener plantillas compartidas.

---

## 🔐 Configuración inicial

Antes de ejecutar cualquier flujo, deben configurarse los siguientes elementos:

### Secrets requeridos
- `APPIAN_DEV_API_KEY`, `APPIAN_QA_API_KEY`, `APPIAN_PROD_API_KEY` — almacenados en los **GitHub Environments** correspondientes.  
- `ICF_JSON_OVERRIDES_QA`, `ICF_JSON_OVERRIDES_PROD` — texto plano con overrides por entorno (Flujo B/C).  
- `GITHUB_TOKEN` — provisto automáticamente por Actions (requerido por el Core).

### Variables de repositorio
- `APP_UUID` (obligatoria) — identificador de la aplicación en Appian.  
- `APP_NAME` (opcional) — nombre legible para etiquetas y releases.

---

## 🚀 Flujos soportados

Los workflows (`deploy-app.yml`, `deploy-package.yml`) permiten seleccionar el plan en el disparo manual (`workflow_dispatch`):

| Flujo | Descripción | Acciones del Core |
| --- | --- | --- |
| **A – Base** | Export → promote directo (sin overrides ni scripts) | `appian-export`, `appian-promote` |
| **B – Package + ICF** | Incluye `customization.properties` por entorno | `appian-export`, `appian-build-icf`, `appian-promote` |
| **C – Extendido** | Export, inspección, scripts SQL y Dev→QA→Prod | `appian-export`, `appian-prepare-db-scripts`, `appian-promote` |

> Cada ejecución publica los artefactos generados y actualiza el release correspondiente. Consulta el Manual de Usuario para pasos detallados, parámetros y políticas de aprobación.

---

## 📄 Formato del secreto (Flujo B/C – overrides)

Los secretos deben contener texto plano con asignaciones en formato:

```
connectedSystem.<UUID>.baseUrl=https://example
connectedSystem.<UUID>.apiKeyValue=AAA
content.<UUID>.VALUE=10
```

**Reglas:**
- Una línea por asignación (`clave=valor`).  
- Líneas vacías o comentadas con `#` se ignoran.  
- Los valores sensibles no se imprimen en logs.  

---

## 🧠 Relación con el Core

El wrapper **no contiene lógica de despliegue propia**: toda la ejecución es delegada al Core.  
Su rol es definir los secretos, variables y workflows que invocan las acciones principales (`export`, `promote`, `build-icf`, etc.).  

Cada aplicación Appian mantiene su propio wrapper, reutilizando el mismo Core compartido.

---

## 📘 Manual de Usuario

Todo el detalle sobre configuración de repositorios, permisos, ejecución de pipelines y tratamiento de incidencias está documentado en:  
[`Manual_de_Usuario_CICD_Appian__GitHub.pdf`](Manual_de_Usuario_CICD_Appian__GitHub.pdf)

Revisa siempre la versión incluida en este repositorio para garantizar que sigues las convenciones vigentes.

## 📞 Contacto y soporte

**Equipo CI/CD Appian – VR Group / Bice Vida**

- Consultor / Developer: Maximiliano Tombolini — mtombolini@vr-group.cl  
- Lead Delivery Service: Ángel Barroyeta — abarroyeta@vrgroup.cl  
- Arquitecto Appian: Ignacio Arriagada — iarriagada@vrgroup.cl  

Utiliza este canal para coordinar nuevas configuraciones, incidentes o mejoras del wrapper. Si necesitas más contexto operativo, consulta el Manual de Usuario antes de escalar.

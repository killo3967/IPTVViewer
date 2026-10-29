# Firma de código con SignPath Foundation

Esta carpeta prepara la firma Authenticode del ejecutable y del instalador. El
workflow ya está modificado: **mientras no existan los secretos, todos los pasos
de firma se saltan y la release se publica igual que antes**.

## Qué hay que hacer una sola vez, a mano

Estas tres cosas no las puede hacer el repositorio por ti:

1. **Solicitar el alta** en <https://signpath.org/apply> con la URL del
   repositorio. Requisitos que revisan: licencia OSI (MIT ✔), sin doble licencia
   comercial, y que el binario se construya desde el repositorio en runners de
   GitHub (✔ `windows-latest`).
2. **Crear en SignPath.io**: organización, proyecto `iptvviewer`, el Trusted
   Build System *GitHub.com* vinculado al proyecto, dos *Artifact
   Configurations* (pegar `exe.xml` con slug `exe` y `setup.xml` con slug
   `setup`) y una *Signing Policy* con slug `release-signing`. Instala también
   la [SignPath GitHub App](https://github.com/apps/signpath) sobre el repo.
3. **Guardar el token** para que el workflow pueda pedir firmas.

## Secretos y variables en GitHub

| Tipo | Nombre | Contenido |
| --- | --- | --- |
| Secret | `SIGNPATH_API_TOKEN` | token de API con permiso de *submitter* |
| Secret | `SIGNPATH_ORGANIZATION_ID` | ID de la organización en SignPath |
| Variable | `SIGNPATH_PROJECT_SLUG` | `iptvviewer` |
| Variable | `SIGNPATH_POLICY_SLUG` | `release-signing` |

Con `gh`:

```bash
gh secret set SIGNPATH_API_TOKEN --repo killo3967/IPTVViewer
gh secret set SIGNPATH_ORGANIZATION_ID --repo killo3967/IPTVViewer
gh variable set SIGNPATH_PROJECT_SLUG --body iptvviewer --repo killo3967/IPTVViewer
gh variable set SIGNPATH_POLICY_SLUG --body release-signing --repo killo3967/IPTVViewer
```

## Qué se firma y en qué orden

1. PyInstaller genera `dist/IPTVViewer.exe` → se sube como artifact y se firma
   (configuración `exe`).
2. El exe firmado sustituye al original y con él se compila el instalador.
3. El instalador se sube como artifact y se firma (configuración `setup`).
4. La release publica el exe firmado y el instalador firmado.

## Verificación

El propio workflow comprueba la firma con `Get-AuthenticodeSignature` y falla si
no es `Valid`. A mano:

```powershell
Get-AuthenticodeSignature .\dist\IPTVViewer.exe | Format-List Status, SignerCertificate
```

## Lo que el usuario verá

El editor será **SignPath Foundation**, no el autor del proyecto: es el trato de
la fundación, que avala con su nombre y su HSM que el binario sale de este
repositorio. La reputación de SmartScreen se acumula por hash, así que la
primera descarga de cada versión puede seguir avisando, pero ya con editor
reconocido en lugar de «desconocido».

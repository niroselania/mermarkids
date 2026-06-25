# MerMarKids Ventas

App web simple para cargar pedidos y gastos de MerMarKids en una sola pantalla.

El archivo principal de la app es `index.html`.

## Funciones

- Alta de pedidos con fecha del dia.
- Calculo automatico de total, seña y resta a abonar.
- Cuentas disponibles: `MARIAN MP`, `MARIAN EF`, `MER MP`, `MER EF`.
- Alta de gastos con efectivo, Mercado Pago y cuenta responsable.
- Resumen de ventas, señas/cobros, resta a cobrar, gastos y caja.
- Exportacion de pedidos y gastos a CSV.

Los datos se guardan en el navegador con `localStorage`. Para uso desde varios dispositivos conviene agregar una base de datos en una segunda etapa.

## Ejecutar con Docker

```bash
docker compose up -d --build
```

Luego abrir:

```text
http://localhost:8088
```

Para cambiar el puerto:

```bash
APP_PORT=8090 docker compose up -d --build
```

## Portainer

1. Subir este proyecto a GitHub.
2. Entrar a Portainer.
3. Ir a `Stacks`.
4. Crear un stack nuevo.
5. Elegir `Repository`.
6. Pegar la URL del repo de GitHub.
7. Usar `docker-compose.yml` como compose path.
8. Deploy the stack.

Por defecto la app queda expuesta en el puerto `8088`.

Si Portainer muestra un error tipo `"/app": not found`, el repo todavia tiene una version vieja del `Dockerfile` o no se subio el archivo `index.html` a la raiz.

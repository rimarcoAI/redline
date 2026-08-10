# Exercise Gym — Ejercicios y Rutinas

Interfaz visual estática (HTML/CSS/JS, sin backend) para explorar la base de
ejercicios de [JahelCuadrado/ExerciseGymGifsDB](https://github.com/JahelCuadrado/ExerciseGymGifsDB)
y crear tus propias rutinas guardadas localmente.

## Qué incluye

- **Explorador de ejercicios**: 1323 ejercicios con su GIF/miniatura, filtrables
  por la clasificación por defecto del dataset (parte del cuerpo, músculo,
  equipamiento y categoría) y por búsqueda de texto.
- **Etiquetas personalizadas**: además de la clasificación de origen, puedes
  añadir tus propias etiquetas a cualquier ejercicio (ej. `#esguincetobillo`)
  desde su ficha de detalle, y filtrar el listado por ellas.
- **Rutinas**: crea rutinas con un título, añade los ejercicios que quieras
  (sin repeticiones ni series, solo la lista de ejercicios) y etiquétalas
  también con tus propias etiquetas. Puedes crear una rutina directamente
  desde una selección múltiple de ejercicios en la vista principal.
- Todo se guarda en el `localStorage` del navegador (etiquetas y rutinas);
  no hay servidor ni base de datos.

## Origen de los datos

Los metadatos de los ejercicios (`data/exercises.js`) se generaron una vez a
partir de `api/es/exercises.json` del repositorio
[ExerciseGymGifsDB](https://github.com/JahelCuadrado/ExerciseGymGifsDB) y se
incluyen "vendorizados" en este proyecto para que la app cargue rápido y no
dependa de una build. Los GIFs/miniaturas **no** se copian: se siguen
sirviendo desde el CDN de jsDelivr del propio repositorio original
(`gifUrl` / `thumbUrl` de cada ejercicio), así que necesitas conexión a
internet para verlos.

Para actualizar los datos a una versión más reciente del dataset, vuelve a
generar `data/exercises.js` a partir de `api/<lang>/exercises.json` del
repo de origen (ver script usado en el histórico de este proyecto).

## Cómo usarlo

Al ser una app 100% estática, la forma más sencilla es servirla con un
servidor HTTP simple (los navegadores bloquean `fetch`/scripts locales al
abrir el `index.html` directamente por `file://` en algunos casos):

```bash
cd exercise-gym
python3 -m http.server 8080
# abre http://localhost:8080 en el navegador
```

## Aviso sobre los GIFs

Los GIFs pertenecen a sus autores originales y se sirven desde el CDN del
repositorio [ExerciseGymGifsDB](https://github.com/JahelCuadrado/ExerciseGymGifsDB),
que recopiló ese material de internet. Consulta su aviso de licencia/derechos
en su propio README.

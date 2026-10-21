# Panel de estado

Genera una página con el estado del proyecto (PRs, issues, personas, equipos) y la publica en GitHub Pages.
No hace commits: no cambia ninguna rama.

La lista de personas se arma sola: colaboradores del repo, asignados a issues, autores de PRs y de commits.
El equipo se deduce del nombre de la rama (`feature/<equipo>-<tarea>`) o de una etiqueta del issue (`equipo:UI`).

Archivos que se pueden editar (ambos opcionales):
- `notas.json`: fecha del próximo entregable, decisiones abiertas y riesgos.
- `equipo.json`: solo para corregir un nombre o equipo, o agregar a alguien que aún no ha hecho nada.

Probar el diseño sin tocar GitHub:
    python scripts/estado/generar.py --salida site_demo --demo

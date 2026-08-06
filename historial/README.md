# historial

Lo genera `actualizar.py`. Es dato, no código, por eso el resto de la carpeta
está en `.gitignore`.

| Archivo | Qué es |
|---|---|
| `estado_actual.csv` | Foto del veredicto de cada lote y batch en la última corrida. Se sobrescribe. Es contra lo que se compara |
| `cambios.csv` | Transiciones de estado. Solo crece. Responde "estuvo bloqueado y después se liberó" |
| `criterios.csv` | Qué reglas estaban vigentes en cada corrida |

Si se borran, el sistema sigue funcionando pero pierde la memoria: la próxima
corrida crea una línea base nueva y las transiciones anteriores no se recuperan.

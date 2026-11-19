# Diccionario de datos · Informe Bolton

## Capa Bronze

### `bronze_bolton`

Ventas de Bolton tal como llegan del Excel. Todas las columnas son `VARCHAR(255)`, los vacíos se guardan como NULL y las columnas se renombran por posición con `COLS_BOLTON` (27 columnas). Se agregan dos columnas de control.

| Columna | Tipo | NULL | Descripción | Encabezado |
|---|---|---|---|---|---|
| `anio` | VARCHAR(255) | Sí | Año de la venta (texto) | AÑO |
| `mes` | VARCHAR(255) | Sí | Mes en nombre inglés (`January` … `December`) | MES |
| `fecha` | VARCHAR(255) | Sí | Fecha de la transacción | — |
| `semana_anio` | VARCHAR(255) | Sí | Número de semana del año | — |
| `semana_mes` | VARCHAR(255) | Sí | Número de semana dentro del mes | — |
| `factura` | VARCHAR(255) | Sí | Número de factura; sirve para detectar duplicados exactos | Factura |
| `documento` | VARCHAR(255) | Sí | Tipo de documento; `FACTURA (-)` marca una devolución | DOCUMENTO |
| `nombre_cliente` | VARCHAR(255) | Sí | Nombre del cliente; `COLOMBOESPAÑOLA` es un traslado interno | Nombre Cliente |
| `canal` | VARCHAR(255) | Sí | Canal de venta (ej. AUTOSERVICIOS) | Canal |
| `articulo` | VARCHAR(255) | Sí | Código del artículo | — |
| `marca` | VARCHAR(255) | Sí | Marca del producto: Puede ser Isabel o Alamar | Marca |
| `texto_breve_material` | VARCHAR(255) | Sí | Descripción corta del material | — |
| `producto` | VARCHAR(255) | Sí | Nombre del producto | Producto |
| `referencia` | VARCHAR(255) | Sí | todos los productos pertenecen a una referencia, suele variar es su gramaje | Referencia |
| `gr` | VARCHAR(255) | Sí | Gramaje del producto en gramos | GR |
| `familia` | VARCHAR(255) | Sí | pueden ser ensaladas de atun, bocados de atun, etc | Familia |
| `categoria` | VARCHAR(255) | Sí | si es en agua, aceite, oliva o tomate | Categoria |
| `punto` | VARCHAR(255) | Sí | Punto de venta | — |
| `ciudad` | VARCHAR(255) | Sí | Territorio comercial de la venta (ej. BOGOTA, SANTANDERES); pasa a `region` en Silver | Ciudad |
| `zona` | VARCHAR(255) | Sí | Zona comercial (ej. NOR ORIENTE) | Zona ||
| `vendedor` | VARCHAR(255) | Sí | Nombre del vendedor | Vendedor |
| `inv` | VARCHAR(255) | Sí | Inventario | — |
| `demand_forecast` | VARCHAR(255) | Sí | Pronóstico de demanda | — |
| `presupuesto` | VARCHAR(255) | Sí | Presupuesto de ventas | — |
| `cajas` | VARCHAR(255) | Sí | Cantidad vendida en cajas | CAJAS |
| `pesos` | VARCHAR(255) | Sí | Valor de la venta en pesos; llega como `844128.0` o `$ 1.101.848,82` | PESOS |
| `euros` | VARCHAR(255) | Sí | Valor de la venta en euros | — |
| `_load_ts` | DATETIME | Sí | Fecha y hora de la carga a MySQL | `load()` |
| `_source_file` | VARCHAR(255) | Sí | Nombre del archivo Excel de origen | `config.yaml: files.bolton_bronze` |


### `bronze_departamentos`

Departamentos de Colombia tal como los entrega la API (CSV). Columnas renombradas por posición con `COLS_DEPTOS` (18 columnas) más dos de control.

| Columna | Tipo | NULL | Descripción |
|---|---|---|---|---|
| `id` | VARCHAR(20) | Sí | Identificador del departamento en API Colombia |
| `name` | VARCHAR(100) | Sí | Nombre del departamento |
| `description` | TEXT | Sí | Descripción del departamento |
| `city_capital_id` | VARCHAR(20) | Sí | Identificador de la ciudad capital |
| `municipalities` | VARCHAR(20) | Sí | Número de municipios |
| `surface` | VARCHAR(30) | Sí | Superficie del departamento km² |
| `population` | VARCHAR(30) | Sí | Población del departamento |
| `phone_prefix` | VARCHAR(20) | Sí | Prefijo telefónico |
| `country_id` | VARCHAR(20) | Sí | Identificador del país |
| `city_capital` | TEXT | Sí | JSON con los datos de la capital (encabezado del CSV: `cityCapital`); `clean_api` extrae el campo `name` |
| `country` | TEXT | Sí | Datos del país |
| `cities` | TEXT | Sí | Ciudades del departamento |
| `region_id` | VARCHAR(20) | Sí | Identificador de la región |
| `region` | TEXT | Sí | Datos de la región |
| `natural_areas` | TEXT | Sí | Áreas naturales |
| `maps` | TEXT | Sí | Datos o enlaces de mapas |
| `indigenous_reservations` | TEXT | Sí | Resguardos indígenas |
| `airports` | TEXT | Sí | Aeropuertos |
| `_load_ts` | DATETIME | Sí | Fecha y hora de la carga a MySQL |
| `_source_file` | VARCHAR(255) | Sí | Nombre del archivo CSV de origen |

## Capa Silver

### Reglas de limpieza de `silver_bolton`

| # | Filas eliminadas | Condición |
|---|---|---|
| 1 | Sin PESOS (forecast, inventario, líneas vacías) | PESOS vacío |
| 2 | PESOS no convertible | No se puede leer como número |
| 3 | Traslado interno | Cliente normalizado contiene `COLOMBOESPANOLA` |
| 4 | Devoluciones | `DOCUMENTO` = `FACTURA (-)` o PESOS < 0 |
| 5 | PESOS = 0 | Valor cero |
| 6 | Periodo incompleto | Año 2026 y mes >= 9 (septiembre a diciembre) |
| 7 | Duplicado exacto con factura | Misma fila completa que otra anterior y con `Factura` no vacía |

Estandarización de texto: mayúsculas, sin tildes, sin espacios sobrantes. Valores vacíos: `SIN CLASIFICAR` para producto, referencia, marca, familia y categoría; `SIN ASIGNAR` para cliente, canal, vendedor, región y zona.

### `silver_areas`

| Columna | Tipo | NULL | Descripción | Origen y regla |
|---|---|---|---|---|---|
| `departamento` | VARCHAR(100) | Sí | Nombre del departamento | `name` sin espacios; se eliminan filas sin nombre |
| `superficie` | INT | Sí | Superficie del departamento | `surface` convertido a número (error → NULL) |
| `poblacion` | BIGINT | Sí | Población del departamento | `population` convertido a número (error → NULL) |
| `ciudad_capital` | VARCHAR(100) | Sí | Nombre de la ciudad capital | Campo `name` del JSON `cityCapital`; NULL si está vacío o no se puede leer |

### `silver_bolton`

| Columna | Tipo | NULL | Descripción | Origen y regla |
|---|---|---|---|---|---|
| `id` | BIGINT AUTO_INCREMENT | No | Identificador de fila (llave primaria) | Generado por MySQL |
| `anio` | SMALLINT | Sí | Año de la venta | `AÑO` convertido a número |
| `mes` | TINYINT | Sí | Mes de la venta (1 a 12) | `MES` en inglés mapeado a número |
| `cliente` | VARCHAR(255) | Sí | Nombre del cliente normalizado | `Nombre Cliente`; vacío → `SIN ASIGNAR` |
| `canal` | VARCHAR(100) | Sí | Canal de venta | `Canal`; vacío → `SIN ASIGNAR` |
| `vendedor` | VARCHAR(150) | Sí | Vendedor | `Vendedor`; vacío → `SIN ASIGNAR` |
| `region` | VARCHAR(100) | Sí | Región comercial (ej. BOGOTA, SANTANDERES) | Viene de la columna `Ciudad` del Excel; vacío → `SIN ASIGNAR` |
| `zona` | VARCHAR(100) | Sí | Zona comercial | `Zona`; vacío → `SIN ASIGNAR` |
| `producto` | VARCHAR(255) | Sí | Nombre del producto | `Producto`; vacío → `SIN CLASIFICAR` |
| `referencia` | VARCHAR(255) | Sí | Referencia del producto | `Referencia`; vacío → `SIN CLASIFICAR` |
| `marca` | VARCHAR(100) | Sí | Marca | `Marca`; vacío → `SIN CLASIFICAR` |
| `familia` | VARCHAR(100) | Sí | Familia de producto | `Familia`; vacío → `SIN CLASIFICAR` |
| `categoria` | VARCHAR(100) | Sí | Categoría de producto | `Categoria`; vacío → `SIN CLASIFICAR` |
| `gr` | DECIMAL(10,2) | Sí | Gramaje en gramos | `GR` a número (error → NULL) |
| `cajas` | DECIMAL(12,2) | Sí | Cantidad vendida en cajas | `CAJAS` a número (error → NULL) |
| `cajas_valida` | BOOLEAN | Sí | Indica si la cantidad de cajas es mayor que cero | `cajas > 0` |
| `pesos` | DOUBLE | Sí | Valor de la venta en pesos (COP) | `PESOS`; acepta `844128.0` y `$ 1.101.848,82` |

### `silver_integrado`

Contiene las 17 columnas de `silver_bolton` sin cambios, más tres columnas del cruce con departamentos.

el config `mapeo_regiones` define qué departamentos componen cada región comercial. Luego se une con Bolton por la región normalizada. Las regiones sin mapeo quedan con las tres columnas en NULL, y el conteo de filas y el total de pesos no deben cambiar.

| Región | N.º de departamentos | Departamentos |
|---|---|---|
| `ANTIOQUIA` | 1 | Antioquia |
| `BOGOTA` | 1 | Bogotá |
| `BOYACA` | 1 | Boyacá |
| `COSTA` | 7 | Atlántico, Bolívar, Magdalena, Cesar, Córdoba, Sucre, La Guajira |
| `CUNDINAMARCA` | 1 | Cundinamarca |
| `EJE CAFETERO` | 3 | Caldas, Risaralda, Quindío |
| `META` | 1 | Meta |
| `SANTANDERES` | 2 | Santander, Norte de Santander |
| `TOLIMA` | 1 | Tolima |
| `VALLE` | 1 | Valle del Cauca |

| Columna | Tipo | NULL | Descripción | Origen y regla |
|---|---|---|---|---|---|
| `departamentos` | VARCHAR(255) | Sí | Departamentos de la región, separados por coma (ej. `Santander, Norte de Santander`) | Nombres según `mapeo_regiones`; NULL si la región no está mapeada |
| `n_departamentos` | TINYINT | Sí | Cantidad de departamentos de la región | Conteo de departamentos del mapeo |
| `poblacion_total` | BIGINT | Sí | Población sumada de los departamentos de la región | Suma de `silver_areas.poblacion` |

## Capa Gold

### `gold_final`


| Columna | Tipo | NULL | Descripción | Origen y regla |
|---|---|---|---|---|---|
| `id` | BIGINT AUTO_INCREMENT | No | Identificador de fila (llave primaria) | Generado por MySQL |
| `anio` | SMALLINT | Sí | Año de la venta | `AÑO` convertido a número |
| `mes` | TINYINT | Sí | Mes de la venta (1 a 12) | `MES` en inglés mapeado a número |
| `cliente` | VARCHAR(255) | Sí | Nombre del cliente normalizado | `Nombre Cliente`; vacío → `SIN ASIGNAR` |
| `canal` | VARCHAR(100) | Sí | Canal de venta | `Canal`; vacío → `SIN ASIGNAR` |
| `vendedor` | VARCHAR(150) | Sí | Vendedor | `Vendedor`; vacío → `SIN ASIGNAR` |
| `region` | VARCHAR(100) | Sí | Región comercial (ej. BOGOTA, SANTANDERES) | Viene de la columna `Ciudad` del Excel; vacío → `SIN ASIGNAR` |
| `zona` | VARCHAR(100) | Sí | Zona comercial | `Zona`; vacío → `SIN ASIGNAR` |
| `producto` | VARCHAR(255) | Sí | Nombre del producto | `Producto`; vacío → `SIN CLASIFICAR` |
| `referencia` | VARCHAR(255) | Sí | Referencia del producto | `Referencia`; vacío → `SIN CLASIFICAR` |
| `marca` | VARCHAR(100) | Sí | Marca | `Marca`; vacío → `SIN CLASIFICAR` |
| `familia` | VARCHAR(100) | Sí | Familia de producto | `Familia`; vacío → `SIN CLASIFICAR` |
| `categoria` | VARCHAR(100) | Sí | Categoría de producto | `Categoria`; vacío → `SIN CLASIFICAR` |
| `gr` | DECIMAL(10,2) | Sí | Gramaje en gramos | `GR` a número (error → NULL) |
| `cajas` | DECIMAL(12,2) | Sí | Cantidad vendida en cajas | `CAJAS` a número (error → NULL) |
| `cajas_valida` | BOOLEAN | Sí | Indica si la cantidad de cajas es mayor que cero | `cajas > 0` |
| `pesos` | DOUBLE | Sí | Valor de la venta en pesos (COP) | `PESOS`; acepta `844128.0` y `$ 1.101.848,82` |
| `departamentos` | VARCHAR(255) | Sí | Departamentos de la región | Sin cambios desde `silver_integrado` |
| `n_departamentos` | TINYINT | Sí | Cantidad de departamentos de la región | Sin cambios desde `silver_integrado` |
| `poblacion_total` | BIGINT | Sí | Población total de la región | Sin cambios desde `silver_integrado` |
| `cuatrimestre` | TINYINT | Sí | Cuatrimestre del año: 1 = ene-abr, 2 = may-ago, 3 = sep-dic | `(mes - 1) // 4 + 1` |
| `periodo_cuatrimestre` | VARCHAR(10) | Sí | Etiqueta del periodo, ej. `2018-C1` | `anio` + `-C` + `cuatrimestre` |

### Informes `gold_<informe>`

Cada informe se genera en generar_informes desde gold_final y se carga como tabla propia.


| Tabla | Agrupa por | Columnas | Filtro / top |
|---|---|---|---|
| `gold_por_anio` | anio | anio, pesos, cajas, n_registros, meses_con_datos | Todos los años (2026 incompleto: solo hasta agosto) |
| `gold_por_cuatrimestre` | anio, cuatrimestre, periodo_cuatrimestre | anio, cuatrimestre, periodo_cuatrimestre, pesos, cajas, n_registros, meses_con_datos | Todos los cuatrimestres |
| `gold_top_ciudades` | anio, region, departamentos | anio, region, departamentos, pesos, cajas, ranking | Top 10 por año. Pese al nombre, agrupa por región, no por ciudad |
| `gold_top_productos` | anio, producto | anio, producto, pesos, cajas, ranking | Top 10 por año |
| `gold_top_vendedores` | anio, vendedor | anio, vendedor, pesos, cajas, ranking | Top 10 por año, sin `SIN ASIGNAR` |
| `gold_top_ventas_per_capita` | anio, region, departamentos | anio, region, departamentos, pesos, cajas, meses_con_datos, poblacion, pesos_per_capita, cajas_per_capita, ranking | Sin mínimo de pesos (`min_pesos_per_capita` no está definido y vale 0); top 10 por año |
| `gold_top_vendedores_per_capita` | anio, vendedor | anio, vendedor, pesos, cajas, meses_con_datos, poblacion, pesos_per_capita, cajas_per_capita, ranking | Sin `SIN ASIGNAR`; población = suma de las regiones donde vendió; top 10 por año |
| `gold_top_productos_cuatrimestre` | anio, cuatrimestre, periodo, producto | anio, cuatrimestre, periodo_cuatrimestre, producto, pesos, cajas, meses_con_datos, participacion_pesos, ranking | Top 5 (`top_n_cuatrimestre`) por cuatrimestre |
| `gold_top_referencias_cuatrimestre` | ídem, con referencia | ídem, con `referencia` | ídem |
| `gold_top_familias_cuatrimestre` | ídem, con familia | ídem, con `familia` | ídem |
| `gold_top_categorias_cuatrimestre` | ídem, con categoría | ídem, con `categoria` | ídem |
| `gold_top_marca_region_cuatrimestre` | anio, cuatrimestre, periodo, region, marca | anio, cuatrimestre, periodo_cuatrimestre, region, marca, pesos, cajas, meses_con_datos, participacion_pesos, ranking | Top 1 (`top_n_marca`) por región y cuatrimestre |
| `gold_top_marca_region_anio` | anio, region, marca | anio, region, marca, pesos, cajas, meses_con_datos, participacion_pesos, ranking | Top 1 (`top_n_marca`) por región y año |

Control en `load()`: la suma de `pesos` de `gold_por_anio` debe coincidir con la de `gold_final` (tolerancia de 1 peso).

#### Glosario de columnas de los informes

| Columna | Tipo | Descripción |
|---|---|---|
| `anio` | SMALLINT | Año |
| `cuatrimestre` | TINYINT | Cuatrimestre del año (1 a 3) |
| `periodo_cuatrimestre` | VARCHAR(10) | Etiqueta `AAAA-Cn`, ej. `2018-C1` |
| `region` | VARCHAR(100) | Región comercial |
| `departamentos` | VARCHAR(255) | Departamentos de la región |
| `producto` | VARCHAR(255) | Producto |
| `referencia` | VARCHAR(255) | Referencia |
| `familia` | VARCHAR(100) | Familia |
| `categoria` | VARCHAR(100) | Categoría |
| `marca` | VARCHAR(100) | Marca |
| `vendedor` | VARCHAR(150) | Vendedor |
| `pesos` | DOUBLE | Suma de ventas en pesos (COP) del grupo |
| `cajas` | DOUBLE | Suma de cajas del grupo |
| `n_registros` | INT | Número de filas de `gold_final` del grupo |
| `meses_con_datos` | TINYINT | Meses distintos con datos dentro del grupo |
| `poblacion` | BIGINT | Población base del per cápita: suma de `poblacion_total` de las regiones distintas del grupo |
| `pesos_per_capita` | DOUBLE | `pesos / poblacion` |
| `cajas_per_capita` | DOUBLE | `cajas / poblacion` |
| `participacion_pesos` | DOUBLE | Fracción (0 a 1) de los pesos del grupo sobre el total del periodo o grupo, calculada antes de recortar al top |
| `ranking` | SMALLINT | Posición dentro del top |


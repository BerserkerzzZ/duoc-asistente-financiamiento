"""
Dataset de evaluación: preguntas donde YA CONOCEMOS la respuesta_esperada correcta,
extraída directamente y a mano de los documentos oficiales.

Esto permite medir la fidelidad del pipeline RAG (¿el agente responde
correctamente lo que dice la normativa?), tal como pide el objetivo del caso:
"precisión superior al 90% en la recuperación de información reglamentaria".

CÓMO COMPLETAR ESTE ARCHIVO (esto lo deben hacer ustedes, revisando sus
propios PDFs):
1. Abran el PDF y busquen un artículo/sección concreta y verificable.
2. Copien la idea central de ese artículo en 'respuesta_esperada' (no hace
   falta copiar textual, basta la idea correcta).
3. Anoten el documento y página exactos en 'fuente_esperada'.
4. Formulen la pregunta como la haría un estudiante real (lenguaje informal).

Con 8-10 pares pregunta/respuesta conocida ya es un dataset de evaluación
razonable para un prototipo de curso.
"""

CASOS_EVALUACION = [
    {
        "pregunta": "¿Cuál es el rol fundamental del formulario FUAS en relación con la obtención de la Gratuidad Universitaria para el proceso 2026?",
        "respuesta_esperada": "El FUAS (Formulario Único de Acreditación Socioeconómica) es el primer paso obligatorio para que los estudiantes accedan a beneficios estatales y financiamiento en la Educación Superior chilena. Al completarlo, los postulantes optan de forma centralizada y conjunta a la Gratuidad, a diversas becas de arancel, a créditos del Estado (Fondo Solidario y Crédito con Garantía Estatal - CAE), y a la Beca de Alimentación otorgada por la JUNAEB.",
        "fuente_esperada": "Instructivo FUAS 2026, Sección '¿Qué es el FUAS?'",
    },
    {
        "pregunta": "Si un estudiante ya es beneficiario vigente de la Gratuidad (renovante) para el año académico siguiente y solo desea mantener dicho beneficio, ¿bajo qué condiciones debe o no debe volver a completar el FUAS?",
        "respuesta_esperada": "Los estudiantes que ya cuentan con Gratuidad, becas y/o créditos en calidad de renovantes, y que únicamente desean mantener sus beneficios vigentes para el año siguiente, NO deben volver a completar el FUAS. La mantención del beneficio está sujeta directamente al cumplimiento de los requisitos académicos de renovación que se detallan en los portales oficiales de Gratuidad y Beneficios Estudiantiles.",
        "fuente_esperada": "Instructivo FUAS 2026, Sección '¿Quiénes deben realizar este proceso?' (Nota especial)",
    },
    {
        "pregunta": "En el proceso de postulación a la Gratuidad a través del FUAS, ¿cómo se calcula exactamente el promedio mensual de ingresos que debe declararse para cada miembro del grupo familiar?",
        "respuesta_esperada": "Para obtener el ingreso promedio mensual de los años 2024 y 2025 de cada integrante del hogar (mayor de 18 años, incluso sin contrato formal), se deben sumar los ingresos brutos mensuales percibidos en cada mes del año respectivo, descontando únicamente las cotizaciones previsionales de carácter obligatorio. Esa suma anual total de ingresos netos se debe dividir por 12. Este promedio calculado es el valor que se ingresa en la casilla correspondiente del formulario.",
        "fuente_esperada": "Instructivo FUAS 2026, Secciones 'Ingresos del grupo familiar', 'Ingresos y promedios' y 'Sueldos'",
    },
    {
        "pregunta": "De acuerdo con el Reglamento Académico de Duoc UC, ¿cuál es el riesgo o impacto que tiene la suspensión de un periodo académico sobre la Gratuidad del estudiante?",
        "respuesta_esperada": "El reglamento establece de forma explícita que, si bien la suspensión exime al alumno del pago de aranceles institucionales durante ese período, los impactos financieros y regulatorios derivados de dicha suspensión son de su exclusiva responsabilidad. En particular, advierte sobre el riesgo de la pérdida del beneficio de la Gratuidad debido a la extensión del plazo total de duración real de la carrera por sobre su duración nominal.",
        "fuente_esperada": "Reglamento Académico Duoc UC 2026, Título XII, Artículo N°51 (Párrafo final sobre impactos de suspensiones)",
    },
    {
        "pregunta": "En el caso de suspensiones amparadas bajo la Ley N° 21.790 (maternidad, paternidad o cuidadores de personas dependientes), ¿qué indica el reglamento académico sobre la mantención de la Gratuidad y cobros asociados?",
        "respuesta_esperada": "Durante la suspensión de estudios justificada bajo la Ley N° 21.790, el estudiante mantendrá vigentes sus beneficios estatales (como la Gratuidad), de acuerdo con lo que dicte dicha legislación (lo cual no es de responsabilidad directa de Duoc UC). Adicionalmente, el reglamento académico estipula que no se devengará el cobro de matrícula ni de arancel por todo el período que se extienda la suspensión aprobada.",
        "fuente_esperada": "Reglamento Académico Duoc UC 2026, Título XII, Artículo N°51 (Letras a y b de la sección 'Durante la suspensión')",
    },
    {
        "pregunta": "Según el Reglamento del Financiamiento Institucional para la Gratuidad (Decreto 333), ¿cuáles son los requisitos socioeconómicos, de nacionalidad y de permanencia exigidos al estudiante para acceder al beneficio?",
        "respuesta_esperada": "El estudiante debe ser chileno, o extranjero con permanencia definitiva o residencia (en este último caso, habiendo cursado su enseñanza media completa en Chile); no poseer un título profesional, técnico de nivel superior o licenciatura de carácter terminal; y provenir de un hogar que pertenezca a los seis primeros deciles de menores ingresos del país.",
        "fuente_esperada": "Reglamento de Gratuidad (Decreto 333), Título II, Artículo 8 (letras a, b y c) y Artículo 10",
    },
    {
        "pregunta": "¿Cuántas veces puede un estudiante cambiarse de carrera o institución manteniendo la Gratuidad, y cómo se calcula el tiempo restante del beneficio en la nueva carrera según el Decreto 333?",
        "respuesta_esperada": "El estudiante beneficiario puede cambiarse de carrera o de institución de educación superior adscrita para mantener su beneficio por una sola vez en total. Una vez realizado el cambio, el beneficio se extenderá por el período de duración nominal de la segunda carrera, pero descontándose obligatoriamente los semestres que el alumno ya haya cursado bajo la cobertura de gratuidad en su carrera de origen.",
        "fuente_esperada": "Reglamento de Gratuidad (Decreto 333), Título IV, Párrafo 3°, Artículo 40",
    },
    {
        "pregunta": "Si un estudiante con Gratuidad excede la duración nominal de su plan de estudios, ¿cuáles son los límites máximos de cobro de arancel y matrícula que la institución educativa puede exigirle?",
        "respuesta_esperada": "Si el estudiante excede la duración nominal de su carrera por hasta un año (primer año de retraso), la institución adscrita solo podrá cobrarle como máximo el 50% del valor total de la suma del arancel regulado y los derechos básicos de matrícula de ese lapso. Si el retraso excede de un año, la institución tiene permitido cobrarle hasta el 100% de la suma del arancel regulado y derechos de matrícula de dichos periodos adicionales.",
        "fuente_esperada": "Reglamento de Gratuidad (Decreto 333), Título III, Párrafo 4°, Artículo 29 (letras a y b)",
    },
]
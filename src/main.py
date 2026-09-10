"""
Punto de entrada del asistente. Loop de conversación simple por consola,
pensado para la demo/presentación del proyecto.

Uso:
    python -m src.main
"""

from src.agent import responder


def main():
    print("=" * 60)
    print("Asistente de Orientación y Beneficios Estudiantiles")
    print("Departamento de Admisión y Financiamiento - Duoc UC")
    print("=" * 60)
    print("Escribe tu pregunta sobre reglamento académico, becas o")
    print("beneficios estatales (gratuidad, CAE, FUAS).")
    print("Escribe 'salir' para terminar.\n")

    while True:
        pregunta = input("Tú: ").strip()

        if not pregunta:
            continue

        if pregunta.lower() in ("salir", "exit", "quit"):
            print("\n¡Gracias por usar el asistente! Que te vaya bien.")
            break

        print("\nAsistente: ", end="", flush=True)
        try:
            respuesta = responder(pregunta)
            print(respuesta)
        except Exception as e:
            print(f"Ocurrió un error al generar la respuesta: {e}")
            print("Verifica tu conexión, tu GROQ_API_KEY y tu MONGO_URI en el .env.")

        print()  # línea en blanco entre turnos, para legibilidad


if __name__ == "__main__":
    main()
from app.db.postgres import initialize_database
from app.ui.gradio_app import create_app

def main():
    initialize_database()
    demo = create_app()
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)

if __name__ == "__main__":
    main()
import gradio as gr

from app.rag.pdf_utils import (
    save_uploaded_pdf,
    get_file_summary,
    get_uploaded_filenames,
    show_file_preview,
)
from app.rag.vectordb import ingest_uploaded_pdfs_to_vectordb
from app.agents.manager import unified_chat_response

def refresh_files():
    return get_file_summary(), gr.update(choices=get_uploaded_filenames(), value=None)

def create_app():
    with gr.Blocks(title="Enterprise AI Assistant - Unified") as demo:
        gr.Markdown(
            """
# Enterprise AI Assistant
## Unified Chat (Manager + Knowledge + SQL Agents)

- Ask HR / policy questions (routed to Knowledge Agent / RAG).
- Ask data / sales questions (routed to SQL Agent / Text-to-SQL).
- The Manager Agent silently chooses the right specialist.
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="Unified Assistant Chat")
                msg = gr.Textbox(
                    label="Ask a question",
                    placeholder=(
                        "Examples:\n"
                        "- How many casual leaves can an employee take?\n"
                        "- Show sales of April.\n"
                        "- Which product generated the highest revenue?"
                    ),
                    lines=3,
                )
                send_btn = gr.Button("Send", variant="primary")
                clear_btn = gr.Button("Clear Chat")

            with gr.Column(scale=1):
                pdf_file = gr.File(
                    label="Upload PDF",
                    file_types=[".pdf"],
                    type="filepath",
                )
                upload_btn = gr.Button("Upload PDF")
                upload_status = gr.Textbox(label="Upload Status", interactive=False)

                ingest_btn = gr.Button("Build Knowledge Base", variant="primary")
                ingest_status = gr.Textbox(label="Knowledge Base Status", interactive=False)

                file_summary = gr.Textbox(
                    label="Uploaded Files Summary",
                    value=get_file_summary(),
                    lines=10,
                    interactive=False,
                )

                refresh_btn = gr.Button("Refresh File List")

                file_dropdown = gr.Dropdown(
                    label="Select Uploaded PDF",
                    choices=get_uploaded_filenames(),
                    interactive=True,
                )

                preview_btn = gr.Button("Show File Preview")
                preview_box = gr.Textbox(
                    label="PDF Preview",
                    lines=12,
                    interactive=False,
                )

        send_btn.click(
            fn=unified_chat_response,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg],
        )

        msg.submit(
            fn=unified_chat_response,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg],
        )

        clear_btn.click(
            fn=lambda: ([], ""),
            inputs=None,
            outputs=[chatbot, msg],
        )

        upload_btn.click(
            fn=save_uploaded_pdf,
            inputs=[pdf_file],
            outputs=[upload_status, file_summary, file_dropdown],
        )

        ingest_btn.click(
            fn=ingest_uploaded_pdfs_to_vectordb,
            inputs=None,
            outputs=[ingest_status],
        )

        refresh_btn.click(
            fn=refresh_files,
            inputs=None,
            outputs=[file_summary, file_dropdown],
        )

        preview_btn.click(
            fn=show_file_preview,
            inputs=[file_dropdown],
            outputs=[preview_box],
        )

    return demo
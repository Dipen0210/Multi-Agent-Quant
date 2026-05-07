import json
import gradio as gr
from finbert_handler import predict, aggregate


def score_headlines(headlines_json: str) -> str:
    """
    API endpoint for the agent to call.
    Input:  JSON string — list of headline strings
    Output: JSON string — {results: [...], aggregate: {...}}
    """
    try:
        headlines = json.loads(headlines_json)
        if not isinstance(headlines, list):
            return json.dumps({"error": "Input must be a JSON array of strings"})
        results = predict(headlines)
        summary = aggregate(results)
        return json.dumps({"results": results, "aggregate": summary})
    except Exception as e:
        return json.dumps({"error": str(e)})


with gr.Blocks(title="QuantSentiment FinBERT") as demo:
    gr.Markdown("## QuantSentiment — Fine-tuned FinBERT\nFinancial news sentiment: negative / neutral / positive")

    with gr.Row():
        with gr.Column():
            inp = gr.Textbox(
                label="Headlines (JSON array)",
                placeholder='["NVDA beats earnings expectations", "Market selloff continues"]',
                lines=4,
            )
            btn = gr.Button("Analyze", variant="primary")
        with gr.Column():
            out = gr.Textbox(label="Result (JSON)", lines=10)

    btn.click(fn=score_headlines, inputs=inp, outputs=out, api_name="score")

    gr.Examples(
        examples=[
            ['["NVIDIA reports record quarterly revenue driven by AI demand"]'],
            ['["Federal Reserve signals further rate hikes amid inflation concerns"]'],
            ['["Apple misses revenue estimates, stock drops 5%"]'],
        ],
        inputs=inp,
    )

if __name__ == "__main__":
    demo.launch()

async function askAgent() {
    const question = document.getElementById("question").value;

    if (!question) {
        alert("Please enter a question");
        return;
    }

    document.getElementById("explanation").innerText = "Thinking...";
    document.getElementById("data").innerText = "";

    const response = await fetch("/api/agent", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: question })
    });

    const result = await response.json();

    if (result.error) {
        document.getElementById("explanation").innerText = result.error;
        return;
    }

    document.getElementById("explanation").innerText =
        result.answer.explanation || "No explanation";

    document.getElementById("data").innerText =
        JSON.stringify(result.answer.data, null, 2);
}

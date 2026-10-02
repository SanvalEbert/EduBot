const iframe = document.querySelector("#iframe");
const button = document.querySelector("button");
button.addEventListener("click", function(e) {
    const iframeDocument = iframe.contentWindow.document;
    const div = iframeDocument.querySelector(".content");
    if (div.classList.contains("success")) {
        div.classList.remove("success");
    } else {
        div.classList.add("success");
    }
});
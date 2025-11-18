function process_messages(messages) {
    if (typeof messages === "string") {
        messages = [messages]
    }
    console.log(typeof messages)
    console.log(messages)
    errorObj = document.getElementById("errors")
    if (errorObj) {
        errorObj.innerHTML = "<li>" + messages.join("</li><li>") + "</li>"
    } else {
        alert(messages.join("\n"));
    }
}
function clear_messages(messages) {
    errorObj = document.getElementById("errors")
    if (errorObj) {
        errorObj.innerHTML = ""
        errorObj.style.display = "none"
    }

}
async function start_preview(){
    try {
        const response = await fetch("/healthcheck/config/preview/start")
        body = await response.text()
        if (!response.ok) {
            throw new Error(response.status + " : " + body);
        }
        clear_messages()
        return body
    } catch(error) {
        process_messages(error.message)
    }
}


async function stop_preview(){
    try {
        const response = await fetch("/healthcheck/config/preview/stop")
        body = await response.text()
        if (!response.ok) {
            throw new Error(response.status + " : " + body);
        }
        return body
    } catch(error) {
        process_messages(error.message)
     }
}


async function reload_dashboard(){
    try {
        const response = await fetch("/healthcheck/reload")
        body = await response.text()
        if (!response.ok) {
            throw new Error(response.status + " : " + body);
        }
        return body
    } catch(error) {
        process_messages(error.message)
     }
}

function start_preview(){
    fetch("/healthcheck/config/preview/start")
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text()
    })
    .then(data => {
        console.log("Succeed to start healthcheck preview");
    })
    .catch(error => {
        console.error('Failed to start healthcheck', error);
     });
}
function stop_preview() {
    fetch("/healthcheck/config/preview/stop")
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text()
    })
    .then(data => {
        console.log("Succeed to stop healthcheck preview");
    })
    .catch(error => {
        console.error('Failed to stop healthcheck', error);
     });

}

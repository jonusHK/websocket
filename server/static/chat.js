// 웹소켓 지원 브라우저 여부 확인
// if (window.WebSocket) {
//     console.log("WebSockets supported.");
// } else {
//    console.log("WebSockets not supported.");
// }

let reconnectTimeout = null;
let selfClosing = false;

function uuidv4() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}

function startAttemptingToEstablishConnection() {
  reconnectTimeout = setTimeout(() => establishWebSocketConnection(), 5000);
}

let uploadedFileStorage = [];

function establishWebSocketConnection() {
    const textView = document.getElementById("text-view");
    const buttonSend = document.getElementById("send-button");
    const buttonStop = document.getElementById("stop-button");
    const userIdView = document.getElementById("invite-user-id");
    const buttonUserInvite = document.getElementById("invite-user");
    const fileInput = document.getElementById("fileUpload");
    const buttonFileSend = document.getElementById("send-files-button");
    const label = document.getElementById("status-label");
    const userProfileId = 1;
    const roomId = 7;
    const socket = new WebSocket(`ws://localhost:8000/api/v1/chats/${userProfileId}/${roomId}`);

    // 연결 성공
    socket.onopen = function (event) {
        label.innerHTML = "연결 성공";

         if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
         }
    }

    // 서버가 데이터 송신 시, OnMessage 이벤트 발생
    socket.onmessage = function (event) {
        let data;
        try {
            const json = JSON.parse(event.data)
            console.log('json - ', json);
            if (json.type === 'message') {
                data = json.data;
                label.innerHTML = label.innerHTML + "<br />" + data.text;
            }
        } catch (e) {
            console.log('Received wrong type message.')
        }
    }

    // 연결 종료
    socket.onclose = function (event) {
        // 비정상적 연결 종료 시, 일정 시간 이후 웹소켓 재연결 시도
        if (selfClosing === false) {
            startAttemptingToEstablishConnection();
            return;
        }

        const code = event.code;
        const reason = event.reason;
        const wasClean = event.wasClean;

        if (wasClean) {
            label.innerHTML = "연결 종료";
        } else {
            label.innerHTML = "연결 종료 " + reason + "(Code: " + code + ")";
        }
    }

    // 예기치 못한 동작이나 오류 발생
    socket.onerror = function (event) {
        label.innerHTML = "에러 발생 - " + event;
    }

    buttonSend.onclick = function () {
        if (socket.readyState === WebSocket.OPEN) {
            const data = {
                'type': 'message',
                'data': {
                    'text': textView.value,
                    'timestamp': Date.now(),
                }
            };
            console.log('send data for message - ', data);
            socket.send(JSON.stringify(data));
        }
    }

    buttonStop.onclick = function () {
        if (socket.readyState === WebSocket.OPEN) {
            selfClosing = true;
            // 여기선 1001 코드 작동 안함 -> 추후 Vue.js 에서 1001로 사용
            socket.close(1001, 'self closing');
        }
    }

    buttonFileSend.onclick = function() {
        if (socket.readyState === WebSocket.OPEN && uploadedFileStorage.length > 0) {
            const data = {
                'type': 'file',
                'data': {
                    'files': uploadedFileStorage.map(elem => {
                        elem.content = elem.content.split(',')[1]
                        return elem
                    }),
                    'timestamp': Date.now()
                }
            }
            console.log('send data for message - ', data);
            socket.send(JSON.stringify(data));
        }
    }


    buttonUserInvite.onclick = function() {
        if (socket.readyState === WebSocket.OPEN) {
            const data = {
                'type': 'invite',
                'data': {
                    'target_user_profile_ids': [userIdView.value],
                    'timestamp': Date.now(),
                }
            }
            console.log('send data for invite - ', data);
            socket.send(JSON.stringify(data));
        }
    }

    const handleFiles = function() {
        const selectedFiles = [...fileInput.files];

        for (let each of selectedFiles) {
            const fileReader = new FileReader();
            fileReader.onload = function(event) {
                const appendElem = document.createElement('div');
                const previewElem = document.createElement('img');
                previewElem.setAttribute('src', event.target.result);
                appendElem.classList.add('preview-image-wrapper');
                appendElem.appendChild(previewElem);
                $('#imagePreviewArea').append(appendElem);
                uploadedFileStorage.push({
                    content: event.target.result,
                    filename: each.name,
                    content_type: each.type
                });
            }
            fileReader.readAsDataURL(each);
        }

        const len = selectedFiles.length;
        const filePreviewElem = $('#imagePreviewArea');
        if (len > 0 && filePreviewElem.hasClass('display-none')) {
            filePreviewElem.removeClass('display-none');
            filePreviewElem.addClass('display-flex');
        } else if (len === 0) {
            filePreviewElem.removeClass('display-flex');
            filePreviewElem.addClass('display-none');
        }
    }

    fileInput.addEventListener("change", handleFiles);
}

window.onload = function() {
    establishWebSocketConnection();
}

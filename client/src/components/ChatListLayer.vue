<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick, onUpdated } from 'vue';
import constants from '../constants';
import _ from 'lodash';
import defaultChatRoomImage from '@/assets/img/anonymous-user.png'

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatListLayer',
    props: {
        chatRooms: Array,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const ws = new WebSocket(`ws://localhost:8000/api/v1/chats/rooms/${proxy.$store.getters['user/getProfileId']}`);
        const state = reactive({
            chatRooms: toRef(props, 'chatRooms'),
            chatRoomImageUrls: {},
        });
        const detailChatRoom = function(room) {
            emit('chatDetail', room.id);
        }
        const infoChatRoom = function(room) {
            emit('chatInfo', room.id);
        }
        const getBackgroundImageUrl = function(urls) {
            let text = '';
            for (const i in urls) {
                if (Number(i) === urls.length - 1) {
                    text += `url(${urls[i]})`;
                } else {
                    text += `url(${urls[i]}), `;
                }
            }
            return text;
        }
        const getBackgroundRepeat = function(urls) {
            let text = '';
            for (const i in urls) {
                if (Number(i) === urls.length - 1) {
                    text += 'no-repeat'
                } else {
                    text += 'no-repeat, '
                }
            }
            return text;
        }
        const getBackgroundSize = function(urls) {
            const size = urls.length;
            if (size === 1) {
                return 'cover';
            } else if (size === 2) {
                return '50%, 50%';
            } else if (size === 3) {
                return '33%, 33%, 33%';
            } else {
                return '25%, 25%, 25%, 25%';
            }

        }
        const getBackgroundPosition = function(urls) {
            const size = urls.length;
            if (size === 1) {
                return '100%';
            } else if (size === 2) {
                return 'left center, right center';
            } else if (size === 3) {
                return 'top center, left center, right center';
            } else {
                return 'top left, top right, bottom left, bottom right';
            }
        }
        const getChatRoomImage = function(obj) {
            if (_.has(state.chatRoomImageUrls, obj.id)) {
                return state.chatRoomImageUrls[obj.id];
            }
            const urlCnt = obj.user_cnt - 1;
            let urls = [];
            if (obj.user_profile_files.length > 0) {
                for (const file of obj.user_profile_files) {
                    if (
                        file.use_type === 'user_profile_image' 
                        && file.is_default === true 
                        && file.user_profile_id !== proxy.$store.getters['user/getProfileId']
                    ) {
                        urls.push(file.url);
                    }
                }
            }
            const requiredUrlCnt = urlCnt - urls.length;
            for (const i of Array(requiredUrlCnt).keys()) {
                urls.push(defaultChatRoomImage);
            }
            if (urls.length > 0) {
                state.chatRoomImageUrls[obj.id] = urls;
            }
            return urls.length > 4 ? urls.slice(0, 4) : urls;
        }
        const getLastChatHistory = function(obj) {
            if (obj.last_chat_history) {
                if (obj.last_chat_history.contents) {
                    return obj.last_chat_history.contents;
                } else if (obj.last_chat_history.files) {
                    const contentType = obj.last_chat_history.files[0].content_type;
                    if (contentType.startsWith('image')) {
                        return '사진을 보냈습니다.';
                    } else if (contentType.startsWith('video')) {
                        return '영상을 보냈습니다.';
                    }
                }
                return '';
            }
            return '';
        }
        const getLastChatHistoryCreated = function(obj) {
            if (obj === null) {
                return null;
            }
            const now = proxy.$dayjs();
            const dt = proxy.$dayjs.unix(obj.timestamp);
            if (now.get('year') === dt.get('year')) {
                if (now.get('month') === dt.get('month') && now.get('date') === dt.get('date')) {
                    return dt.format('A h:mm');
                } else if (now.diff(dt, 'day') <= 1) {
                    return '어제';
                } else {
                    return dt.format('M월 D일');
                }
            }
            return dt.format('YY-MM-DD.');
        }
        return {
            state,
            proxy,
            detailChatRoom,
            infoChatRoom,
            getBackgroundImageUrl,
            getBackgroundRepeat,
            getBackgroundSize,
            getBackgroundPosition,
            getChatRoomImage,
            getLastChatHistory,
            getLastChatHistoryCreated,
        }
    }
}
</script>

<template>
    <div class="chat-body-list" v-if="state.chatRooms">
        <div v-for="obj in state.chatRooms" :key="obj.id" class="chat-room-list" @click="detailChatRoom(obj)">
            <div class="chat-room-image" :style="{
                backgroundImage: getBackgroundImageUrl(getChatRoomImage(obj)),
                backgroundRepeat: getBackgroundRepeat(getChatRoomImage(obj)),
                backgroundSize: getBackgroundSize(getChatRoomImage(obj)),
                backgroundPosition: getBackgroundPosition(getChatRoomImage(obj)),
            }" @click="infoChatRoom(obj)"></div>
            <div class="chat-room-info">
                <div class="chat-room-info-summary">
                    <p class="chat-room-info-name"><b>{{ obj.name }}</b></p>
                    <p class="chat-room-info-last-chat">{{ getLastChatHistory(obj) }}</p>
                </div>
                <div class="chat-room-info-meta">
                    <div class="chat-room-info-time">{{ getLastChatHistoryCreated(obj.last_chat_history) }}</div>
                    <div v-if="obj.unread_msg_cnt > 0">
                        <div class="unread-msg-cnt-icon-div">
                            <p class="unread-msg-cnt-icon"></p>
                        </div>
                        <p class="unread-msg-cnt">{{ obj.unread_msg_cnt }}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.chat-room-list {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    padding: 15px;
    cursor: pointer;
}

.chat-room-list:hover {
    background-color: #f5f5f5;
}

.chat-room-image-default {
    width: 40px; 
    height: 40px; 
    margin: 0 10px 0 0;
    border-radius: 50%; 
    background-color: #81d4fa;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.chat-room-image {
    width: 40px; 
    height: 40px; 
    margin: 0 10px 0 0; 
    border-radius: 20%; 
}

.chat-room-info {
    width: 100%;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
}

.chat-room-info-name {
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
}

.chat-room-info-last-chat {
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
}

.chat-room-info-summary {
    overflow: hidden;
}

.chat-room-info-summary p {
    height: 20px;
    margin: 5px;
}

.chat-room-info-summary p:nth-child(2) {
    color: #757575;
}

.chat-room-info-meta {
    width: 90px;
}

.chat-room-info-meta div {
    height: 20px;
    margin: 5px;
    text-align: center;
}

.chat-room-info-meta p {
    margin: 0px;

}

.chat-room-info-time {
    color: #757575;
}

.unread-msg-cnt-icon-div {
    display: flex; 
    justify-content: center;
}

.unread-msg-cnt-icon {
    width: 20px;
    height: 20px;
    border-radius: 50%; 
    background-color: #e53935;
}

.unread-msg-cnt {
    position: relative;
    bottom: 23px;
    font-size: 14px;
    color: #ffffff;
}
</style>

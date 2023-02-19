<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick, onUpdated } from 'vue';
import constants from '../constants';
import _ from 'lodash';
import defaultProfileImage from '@/assets/img/anonymous-user.png'

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'ChatListLayer',
    props: {
        chatRooms: Array,
        chatRoomId: Number,
    },
    setup (props, { emit }) {
        const { proxy } = getCurrentInstance();
        const state = reactive({
            chatRooms: [],
            currentChatRoomId: toRef(props, 'chatRoomId'),
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
                return '100%';
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
                return 'center center';
            } else if (size === 2) {
                return 'left center, right center';
            } else if (size === 3) {
                return 'top center, left center, right center';
            } else {
                return 'top left, top right, bottom left, bottom right';
            }
        }
        const getProfileImages = function(obj) {
            let urls = [];
            if (obj.user_profile_files !== null && obj.user_profile_files.length > 0) {
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
            const requiredUrlCnt = obj.user_profiles.length === 1 ? obj.user_profiles.length - urls.length : obj.user_profiles.length - urls.length - 1;
            if (requiredUrlCnt > 0) {
                for (const i of Array(requiredUrlCnt).keys()) {
                    urls.push(defaultProfileImage);
                }
            }
            return urls.length > 4 ? urls.slice(0, 4) : urls;
        }
        const profileImageStyle = function(size, index) {
            const baseStyle = {
                position: 'absolute',
                margin: 0,
            }
            const attribute = {};
            switch (size) {
                case 1:
                    return {
                        width: '100%',
                        height: '100%'
                    };
                case 2:
                    if (index === 0) {
                        _.assign(attribute, {
                            top: 0,
                            left: 0,
                             zIndex: 1
                        });
                    } else {
                        _.assign(attribute, {
                            bottom: 0,
                            right: 0,
                            zIndex: 2
                        })
                    }
                    return {
                        ...baseStyle,
                        ...attribute,
                        width: '62%',
                        height: '62%'
                    };
                case 3:
                    if (index === 0) {
                        _.assign(attribute, {
                            top: 0,
                            left: '8px',
                            zIndex: 3,
                        });
                    } else if (index === 1) {
                        _.assign(attribute, {
                            bottom: 0,
                            left: 0,
                            zIndex: 1,
                        });
                    } else {
                        _.assign(attribute, {
                            bottom: 0,
                            right: 0,
                            zIndex: 2,
                        });
                    }
                    return {
                        ...baseStyle,
                        ...attribute,
                        width: '55%',
                        height: '55%',
                    };
                case 4:
                    if (index === 0) {
                        _.assign(attribute, {
                            top: 0,
                            left: 0,
                            zIndex: 1,
                        });
                    } else if (index === 1) {
                        _.assign(attribute, {
                            top: 0,
                            right: 0,
                            zIndex: 3,
                        });
                    } else if (index === 2) {
                        _.assign(attribute, {
                            bottom: 0,
                            left: 0,
                            zIndex: 2,
                        });
                    } else {
                        _.assign(attribute, {
                            bottom: 0,
                            right: 0,
                            zIndex: 4,
                        });
                    }
                    return {
                        ...baseStyle,
                        ...attribute,
                        width: '50%',
                        height: '50%',
                    }
            }
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
            if (obj.last_chat_history === null) {
                return null;
            }
            const now = proxy.$dayjs();
            const dt = proxy.$dayjs.unix(obj.last_chat_history.timestamp);
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
        const getUnreadMsgCnt = function(obj) {
            return obj.unread_msg_cnt > 99 ? '99+' : obj.unread_msg_cnt;
        }
        const getUserCnt = function(obj) {
            return obj.user_profiles.length > 2 ? obj.user_profiles.length : null;
        }
        watch(
            () => props.chatRooms,
            (cur) => {
                state.chatRooms = cur;
            },
        )
        return {
            state,
            proxy,
            detailChatRoom,
            infoChatRoom,
            getBackgroundImageUrl,
            getBackgroundRepeat,
            getBackgroundSize,
            getBackgroundPosition,
            getProfileImages,
            profileImageStyle,
            getLastChatHistory,
            getLastChatHistoryCreated,
            getUnreadMsgCnt,
            getUserCnt,
        }
    }
}
</script>

<template>
    <div class="chat-body-list" v-if="state.chatRooms">
        <div v-for="obj in state.chatRooms" :key="obj.id" class="chat-room-list" @click="detailChatRoom(obj)">
            <div class="chat-room-image-container">
                <div 
                    v-for="(url, index) in getProfileImages(obj)" 
                    :key="index" 
                    :style="profileImageStyle(getProfileImages(obj).length, index)"
                >
                    <img class="chat-room-image" :src="url" alt="Image" />
                </div>
            </div>
            <div class="chat-room-info">
                <div class="chat-room-info-summary">
                    <p class="chat-room-info-name"><b>{{ obj.name }}</b><span class="chat-room-info-user-cnt">&nbsp;&nbsp;{{ getUserCnt(obj) }}</span></p>
                    <p class="chat-room-info-last-chat">{{ getLastChatHistory(obj) }}</p>
                </div>
                <div class="chat-room-info-meta">
                    <div class="chat-room-info-time">{{ getLastChatHistoryCreated(obj) }}</div>
                    <div v-if="obj.id !== state.currentChatRoomId && obj.unread_msg_cnt > 0">
                        <div class="unread-msg-cnt-icon-div">
                            <p class="unread-msg-cnt-icon"></p>
                        </div>
                        <p class="unread-msg-cnt">{{ getUnreadMsgCnt(obj) }}</p>
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

.chat-room-image-container {
    width: 45px; 
    height: 45px;
    position: relative;
}

.chat-room-image {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    border: 2px solid #ffffff;
    object-fit: cover;
    object-position: center;
}

.chat-room-info {
    width: 100%;
    margin-left: 10px;
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

.chat-room-info-user-cnt {
    color: #9e9e9e;
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
    font-size: 14px;
    color: #757575;
}

.unread-msg-cnt-icon-div {
    display: flex; 
    justify-content: center;
}

.unread-msg-cnt-icon {
    width: 26px;
    height: 26px;
    border-radius: 50%; 
    background-color: #e53935;
}

.unread-msg-cnt {
    position: relative;
    bottom: 20px;
    font-size: 14px;
    color: #ffffff;
}
</style>

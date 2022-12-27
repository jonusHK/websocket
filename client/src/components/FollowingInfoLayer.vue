<script>
import { reactive, watch, onMounted, getCurrentInstance, toRef, nextTick } from 'vue';
import constants from '../constants';

const { VITE_SERVER_HOST } = import.meta.env;


export default {
    name: 'FollowingListLayer',
    props: {
      userProfileId: Number
    },
    setup (props, { emit }) {
      const { proxy } = getCurrentInstance();
      const state = reactive({
        loginProfileId: proxy.$store.getters['user/getProfileId'],
        profileId: toRef(props, 'userProfileId'),
        profileNickname: '',
        profileStatusMessage: '',
        profileImages: [],
        profileDefaultImage: '',
        profileRelationship: '',
        profileIsDefault: false,
        profileIsActive: true,
      });
      const getUserProfileDetail = async function(profileId) {
        proxy.$axios.get(VITE_SERVER_HOST + `/users/profile/${state.loginProfileId}/${profileId}`)
        .then((res) => {
            if (res.status === 200) {
                state.profileNickname = res.data.data.nickname;
                state.profileStatusMessage = res.data.data.status_message;
                state.profileImages = res.data.data.images;
                state.profileDefaultImage = getDefaultProfileImage(state.profileImages);
                state.profileRelationship = res.data.data.relationship;
                state.profileIsDefault = res.data.data.is_default;
                state.profileIsActive = res.data.data.is_active;
            }
        })
        .catch((err) => {
            proxy.$alert({
                state: 'error',
                stateOutlined: true,
                message: err.response.data.message,
            })
        })
        await nextTick();
      }
      const getDefaultProfileImage = function(images) {
        for (const idx in images) {
            const image = images[idx];
            if (constants.profileImageType[image.type] === 'profile' && image.is_default === true) {
                return image.url;
            }
        }
        return null;
      }
      const closeFollowingInfo = function() {
        emit('closeFollowingInfo');
      }
      const followingHidden = function(profileId) {
        proxy.$axios.patch(VITE_SERVER_HOST + `/users/relationship/${state.loginProfileId}/${profileId}`, JSON.stringify({
            is_hidden: true,
        }), {
            headers: {
                "Content-Type": `application/json`,
            },
        })
        .then((res) => {
            if (res.status === 200) {
                proxy.$alert({
                    message: '숨김 처리하였습니다.',
                    state: 'success',
                    stateOutlined: true
                })
                proxy.$router.replace('/');
            }
        })
      }
      const followingForbidden = function(profileId) {
        proxy.$axios.patch(VITE_SERVER_HOST + `/users/relationship/${state.loginProfileId}/${profileId}`, JSON.stringify({
            is_forbidden: true,
        }), {
            headers: {
                "Content-Type": `application/json`,
            },
        })
        .then((res) => {
            if (res.status === 200) {
                proxy.$alert({
                    message: '차단 완료하였습니다.',
                    state: 'success',
                    stateOutlined: true
                })
                proxy.$router.replace('/');
            }
        })
      }
      watch(
        () => props.userProfileId,
        (cur, prev) => {
            getUserProfileDetail(cur)
        },
      )
      onMounted(() => {
        getUserProfileDetail(state.profileId);
      })
      return {
        state,
        getUserProfileDetail,
        getDefaultProfileImage,
        closeFollowingInfo,
        followingHidden,
        followingForbidden,
      }
    }
}
</script>

<template>
    <div class="chat-body-info-summary">
        <div style="font-size: 20px;">
            <p><b>프로필</b></p>
            <ui-icon @click="closeFollowingInfo()" style="color: #9e9e9e; cursor: pointer;">close</ui-icon>
        </div>
    </div>
    <div class="chat-body-info-view">
        <div class="profile-image-layout">
            <div 
                class="profile-image"
                v-if="state.profileDefaultImage !== null"
                :style="{
                    backgroundImage: 'url(' + state.profileDefaultImage + ')',
                    backgroundRepeat: 'no-repeat',
                    backgroundSize: 'cover'
                }"
            ></div>
            <div v-else class="profile-image-default">
                <div><ui-icon style="width: 100%; height: 100%; color: #b3e5fc" :size="48">person</ui-icon></div>
            </div>
        </div>
        <div class="profile-info-layout">
            <p>{{ state.profileNickname }}</p>
            <p>{{ state.profileStatusMessage }}</p>
        </div>
        <div class="profile-interaction-btn-layout">
            <div v-if="state.profileRelationship === null" class="profile-interaction-btn">
                <p><ui-icon>person_add</ui-icon></p>
                <p>친구 추가</p>
            </div>
            <div v-else class="profile-interaction-btn">
                <div>
                    <p><ui-icon>chat_bubble_outline</ui-icon></p>
                    <p>1:1 대화</p>
                </div>
                <div @click="followingHidden(state.profileId)">
                    <p><ui-icon>lens_blur</ui-icon></p>
                    <p>숨김</p>
                </div>
                <div @click="followingForbidden(state.profileId)">
                    <p><ui-icon>block</ui-icon></p>
                    <p>차단</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.profile-image-layout {
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.profile-image {
    width: 250px;
    height: 250px;
    border-radius: 5%;
}

.profile-image-default {
    width: 250px;
    height: 250px;
    border-radius: 5%;
    margin: 0;
    background-color: #81d4fa;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.profile-info-layout {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 15px;
    padding-bottom: 15px;
    border-bottom: 1px solid #e0e0e0;
}

.profile-info-layout p {
    margin: 5px;
}

.profile-info-layout p:nth-child(1) {
    font-size: 20px;
    font-weight: bold;
}

.profile-info-layout p:nth-child(2) {
    font-size: 17px;
    min-height: 21px;
    color: #9e9e9e;
}

.profile-interaction-btn-layout {
    width: 100%;
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
}

.profile-interaction-btn {
    display: flex;
    flex-direction: row;
    justify-content: center;
}

.profile-interaction-btn div {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1 1 0;
    width: 50px;
    margin: 20px;
    cursor: pointer;
}
</style>
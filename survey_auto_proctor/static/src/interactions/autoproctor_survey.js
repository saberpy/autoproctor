/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import { loadJS } from "@web/core/assets";


const CLIENT_ID = 'alD5CxBT'
const CLIENT_SECRET = 'gexcTV6jcboEqYa' 
// const AUTOPROCTOR_SDK_URL = "https://cdn.autoproctor.co/ap-entry.js";

publicWidget.registry.AutoProctor = publicWidget.Widget.extend({
    selector: '.o_survey_form, .o_survey_fill_form, .o_survey-fill-form',

    events: {
        'click button[type="submit"][value="start"]': '_onStartClick',
        // 'click button[type="submit"][value="next"]': '_onNextClick',
        'click button[type="submit"][value="finish"]': '_onFinishClick',
        'submit form': '_onSubmitForm',
    },

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);
        this.apInst = null;
        this.isSubmitting = false;

        const elData = this.el.dataset;
        this.isAutoProctorEnabled = elData.autoproctorEnabled === "1" || elData.autoproctorEnabled === "true";
        this.stopSurveyWithAutoproctor = elData.stopSurveyWithAutoproctor === "1" || elData.stopSurveyWithAutoproctor === "true";
        this.answerToken = elData.answerToken;
        this.stopScore = elData.autoproctorStopScore;
        this.surveyToken = elData.surveyToken;

        // شنیدن ایونت‌های جهانی AutoProctor
        this._bindAutoProctorEvents();

        // اگر آزمون قبلاً شروع شده و کاربر روی صفحه اول (Start Screen) نیست
        const isStartScreen = elData.isStartScreen === "True" || elData.isStartScreen === "true";
        if (this.isAutoProctorEnabled && !isStartScreen && this.answerToken) {
            await this._initAndStartAutoProctor();
        }
    },
    async computeHash(message, secret) {
        const enc = new TextEncoder()
        const key = await crypto.subtle.importKey(
            'raw', enc.encode(secret),
            { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
        )
        const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message))
        return btoa(String.fromCharCode(...new Uint8Array(sig)))
    },

    /**
     * ثبت listener برای رویدادهای AutoProctor
     */
    _bindAutoProctorEvents() {
        window.addEventListener('apMonitoringStarted', () => {
            console.log("AutoProctor: Monitoring has started successfully.");
        });

        window.addEventListener('apMonitoringStopped', () => {
            console.log("AutoProctor: Monitoring stopped.");
        });
    },

    /**
     * کلیک روی دکمه شروع آزمون
     */
    async _onStartClick(ev) {
        if (!this.isAutoProctorEnabled) {
            return;
        }

        this.answerToken = this.el.dataset.answerToken || this.answerToken;

        if (this.answerToken) {
            try {
                await this._initAndStartAutoProctor();
            } catch (error) {
                console.error("AutoProctor start failed:", error);
            }
        }
    },

    // async _onNextClick(ev){
    //     console.log("Next Clicked")
    //     const report = await this.apInst.getReport()
    //     console.log(report)

    // },

    /**
     * کلیک روی دکمه اتمام آزمون
     */
    async _onFinishClick(ev) {
        this.isSubmitting = true;
        await this._stopAutoProctor();
    },

    /**
     * مدیریت Submit شدن فرم Odoo
     */
    _onSubmitForm(ev) {
        const isLastPage = this.$('button[type="submit"][value="finish"]').length > 0;
        if (isLastPage || this.isSubmitting) {
            this._stopAutoProctor();
        }
    },

    /**
     * بارگیری SDK، دریافت Credentials و راه‌اندازی AutoProctor
     */
    async _initAndStartAutoProctor() {
        if (this.apInst) {
            return; // جلوگیری از اجرای مجدد
        }

        // ۱. بارگیری فایل SDK
        // await loadJS(AUTOPROCTOR_SDK_URL);

        if (typeof window.AutoProctor === "undefined") {
            console.error("AutoProctor SDK is not available.");
            return;
        }

        // ۲. دریافت Credentials از پایتون (تولید HMAC-SHA256 در بک‌اند)
        async function computeHash(message, secret) {
            const enc = new TextEncoder()
            const key = await crypto.subtle.importKey(
                'raw', enc.encode(secret),
                { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
            )
            const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message))
            return btoa(String.fromCharCode(...new Uint8Array(sig)))
        }

        const hashedTestAttemptId = await computeHash(this.answerToken, CLIENT_SECRET)
        const credentials = {
            clientId: CLIENT_ID,
            testAttemptId: this.answerToken,
            hashedTestAttemptId: hashedTestAttemptId
        }
        if (!credentials || credentials.error || !credentials.clientId) {
            console.error("AutoProctor credentials error:", credentials?.error || "Invalid response");
            return;
        }
        console.log("Hashed Attempt id is : ", hashedTestAttemptId)
        await rpc(
            `/survey/autoproctor/event/addattemptid`,
            {
                'survey_token': this.surveyToken,
                'answer_token': this.answerToken,
                'test_attempt_id': hashedTestAttemptId,
            }
        );

        const proctoringOptions = {
            trackingOptions: {
                // auxiliaryDevice: true,
                audio: true,
                numHumans: true,
                tabSwitch: true,
                photosAtRandom: true
            },
            // auxDeviceContainerId: 'aux-device-container'
        };

        this.apInst = new window.AutoProctor(credentials);
        await this.apInst.setup(proctoringOptions);
        this.apInst.start();
    },

    /**
     * متوقف کردن نظارت AutoProctor
     */
    async _stopAutoProctor() {
        if (this.apInst) {
            try {
                await this.apInst.stop();
                this.apInst = null;
            } catch (error) {
                console.error("Error stopping AutoProctor:", error);
            }
        }
    },

    /**
     * @override
     */
    destroy() {
        this._stopAutoProctor();
        this._super(...arguments);
    }
});

export default publicWidget.registry.AutoProctor;
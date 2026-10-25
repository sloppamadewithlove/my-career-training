package menus
{
    import com.adobe.serialization.json.JSON;
    import flash.events.Event;
    import flash.events.IOErrorEvent;
    import flash.events.SecurityErrorEvent;
    import flash.events.TimerEvent;
    import flash.net.URLLoader;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.utils.ByteArray;
    import flash.utils.Timer;
    import flash.utils.getTimer;
    import projectx.core.UIMenu;
    import projectx.core.UIScreen;
    import scaleform.clik.constants.NavigationCode;
    import scaleform.clik.controls.Button;
    import scaleform.clik.events.InputEvent;
    import scaleform.gfx.TextFieldEx;
    import tagame.api.DevUtil;
    import tagame.core.ITAGameShell;
    import tagame.core.TAGameShellInstance;

    // Authored pause controls. The document screen still owns pause, unpause,
    // and input release. Resume and Options run only while this menu is front.
    public class MctPauseMenu extends MidGameMenu
    {
        private static const VIEW_URL:String = "__MCT_VIEW_URL__";
        private static const SESSION:String = "__MCT_SESSION__";
        private static const SURFACE:String = "pause";
        private static const BODY_UTF8_MAX:int = 1536;
        private var timer:Timer;
        private var loader:URLLoader;
        private var loadStarted:int;
        private var view:Object;
        private var generation:String = "";
        private var attached:Boolean = false;
        private var busy:Boolean = false;
        private var busyStarted:int = 0;
        private var heldBack:Boolean = false;
        private var lastHello:int = -1000;
        private var details:TextField;

        public function MctPauseMenu()
        {
            super();
            details = new TextField();
            details.multiline = true;
            details.wordWrap = true;
            details.selectable = false;
            details.mouseEnabled = false;
            details.tabEnabled = false;
            details.defaultTextFormat = new TextFormat("Arial", 20, 0xFFFFFF);
            addChild(details);
        }

        override protected function handleAddedToStage(event:Event) : void
        {
            super.handleAddedToStage(event);
            attached = true;
            if (timer == null)
            {
                timer = new Timer(250);
                timer.addEventListener(TimerEvent.TIMER, poll, false, 0, true);
            }
            timer.start();
            poll();
        }

        override protected function handleRemovedFromStage(event:Event) : void
        {
            attached = false;
            closeLoader();
            if (timer != null && !UIMenu.isMenuInStack(menuName)) timer.stop();
            super.handleRemovedFromStage(event);
        }

        override protected function handleInput(event:InputEvent) : void
        {
            // Vertical authored buttons keep focus. RIGHT is the inherited
            // Friends handoff, so it is not forwarded. Escape and Start still
            // reach the stock resume close.
            if (event != null && event.details != null && event.details.navEquivalent == NavigationCode.RIGHT)
            {
                event.handled = true;
                return;
            }
            super.handleInput(event);
        }

        override protected function refreshMenu() : void
        {
            super.refreshMenu();
            layoutDetails();
            x = UIScreen.ContentStageWidth * 0.5;
            y = Math.max(0, (UIScreen.ContentStageHeight - height) * 0.5);
        }

        override protected function handleStageResized(event:Event = null) : void
        {
            layoutDetails();
            super.handleStageResized(event);
        }

        // Live bounds: the field is inside the stock pause panel, in the authored
        // button column. x and width come from the first button (stock column is
        // centered, 260 wide). y is 8px under the lowest button. Height is at
        // least 48 and stops so background.height stays within
        // ContentStageHeight - 40. The panel then grows to text bottom + 16 and
        // recenters with x = ContentStageWidth / 2 and
        // y = (ContentStageHeight - height) / 2. Stage resize repeats that.
        // Wrapped title and body stay inside that rectangle: 20px, then smaller
        // by 1px down to 10px while textHeight exceeds it, then TextFieldEx shrink.
        private function layoutDetails() : void
        {
            if (details == null || background == null) return;
            var columnX:Number = -130;
            var columnW:Number = 260;
            var columnBottom:Number = m_initButtonPosY;
            if (m_buttons.length > 0)
            {
                var first:Button = m_buttons[0] as Button;
                if (first != null)
                {
                    columnX = first.x;
                    columnW = first.width > 1 ? first.width : 260;
                    if (first.textField != null)
                    {
                        var format:TextFormat = first.textField.defaultTextFormat;
                        format.size = 20;
                        format.color = 0xFFFFFF;
                        details.defaultTextFormat = format;
                    }
                }
                for each (var button:Button in m_buttons)
                {
                    var bottom:Number = button.y + (button.height > 1 ? button.height : 33);
                    if (bottom > columnBottom) columnBottom = bottom;
                }
            }
            var maxPanel:Number = Math.max(columnBottom + 72, UIScreen.ContentStageHeight - 40);
            details.x = columnX;
            details.y = columnBottom + 8;
            details.width = columnW;
            details.height = Math.max(48, Math.min(280, maxPanel - details.y - 16));
            showFitted(current() ? String(view.title) + "\n\n" + String(view.body) : "Paused\n\nWaiting for the offline career service.");
            background.height = details.y + details.height + 16;
        }

        private function showFitted(copy:String) : void
        {
            var format:TextFormat = details.defaultTextFormat;
            if (format == null) format = new TextFormat("Arial", 20, 0xFFFFFF);
            var size:int = 20;
            while (size >= 10)
            {
                format.size = size;
                details.defaultTextFormat = format;
                details.text = copy;
                details.setTextFormat(format);
                if (details.textHeight <= details.height - 4) break;
                size--;
            }
            TextFieldEx.setTextAutoSize(details, TextFieldEx.TEXTAUTOSZ_SHRINK);
        }

        override protected function refreshButtons() : void
        {
            var focusName:String = currentFocus != null ? currentFocus.name : "";
            var resumeButton:Button = null;
            var made:Button = null;
            destroyButtons();
            if (!current())
            {
                createButton({label:"PAUSED", enabled:false});
                return;
            }
            for each (var item:Object in view.controls)
            {
                if (!usable(item)) continue;
                made = createButton({name:String(item.id), label:String(item.label),
                    enabled:item.enabled === true && !busy}, choose, [item]);
                if (item.stock === "resume") resumeButton = made;
            }
            if (focusName != "")
            {
                for each (var existing:Button in m_buttons)
                {
                    if (existing.name == focusName && existing.enabled)
                    {
                        currentFocus = existing;
                        return;
                    }
                }
            }
            if (resumeButton != null) currentFocus = resumeButton;
            else if (m_buttons.length > 0) currentFocus = m_buttons[0] as Button;
        }

        private function choose(item:Object) : void
        {
            if (!isFrontMenu() || !current() || item == null || item.enabled !== true) return;
            var present:Boolean = false;
            for each (var candidate:Object in view.controls)
                if (candidate === item) present = true;
            if (!present || String(view.generation) != generation) return;
            if (item.stock === "resume")
            {
                close();
                return;
            }
            if (item.stock === "options")
            {
                if (m_shell != null) openOptionsMenu();
                return;
            }
            if (item.stock != null && item.stock !== "") return;
            if (busy) return;
            busy = true;
            busyStarted = getTimer();
            DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1, session:SESSION,
                surface:SURFACE, generation:generation, revision:String(item.revision), control:String(item.id)}));
            refreshMenu();
        }

        private function poll(event:TimerEvent = null) : void
        {
            if (!attached && !UIMenu.isMenuInStack(menuName)) return;
            if (view != null && !current()) loseConnection();
            if (loader != null)
            {
                if (getTimer() - loadStarted < 1500) return;
                closeLoader();
            }
            if (VIEW_URL.indexOf("file:///") != 0 || SESSION.indexOf("__MCT_") == 0) return;
            loader = new URLLoader();
            loader.addEventListener(Event.COMPLETE, loaded, false, 0, true);
            loader.addEventListener(IOErrorEvent.IO_ERROR, failed, false, 0, true);
            loader.addEventListener(SecurityErrorEvent.SECURITY_ERROR, failed, false, 0, true);
            loadStarted = getTimer();
            try { loader.load(new URLRequest(decodeURIComponent(VIEW_URL.substr(8)))); }
            catch (error:Error) { failed(); }
        }

        private function loaded(event:Event) : void
        {
            if (loader == null || event.currentTarget !== loader) return;
            var raw:String = String(loader.data);
            closeLoader();
            if (raw.length > 65536) { loseConnection(); return; }
            try
            {
                var incoming:Object = com.adobe.serialization.json.JSON.decode(raw, true);
                if (!acceptable(incoming)) throw new Error("Invalid menu");
                if (getTimer() - lastHello >= 1000)
                {
                    DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1,
                        session:SESSION, surface:SURFACE, generation:String(incoming.generation), event:"ready"}));
                    lastHello = getTimer();
                }
                if (!isFrontMenu())
                {
                    view = incoming;
                    heldBack = true;
                    return;
                }
                var next:String = String(incoming.generation);
                if (heldBack || next != generation)
                {
                    heldBack = false;
                    view = incoming;
                    generation = next;
                    busy = false;
                    refreshMenu();
                }
                else
                {
                    view.published_at = incoming.published_at;
                    if (busy && getTimer() - busyStarted >= 2000)
                    {
                        busy = false;
                        refreshMenu();
                    }
                }
            }
            catch (error:Error) { loseConnection(); }
        }

        private function failed(event:Event = null) : void
        {
            closeLoader();
            if (!current()) loseConnection();
        }

        private function closeLoader() : void
        {
            if (loader == null) return;
            loader.removeEventListener(Event.COMPLETE, loaded);
            loader.removeEventListener(IOErrorEvent.IO_ERROR, failed);
            loader.removeEventListener(SecurityErrorEvent.SECURITY_ERROR, failed);
            try { loader.close(); } catch (error:Error) {}
            loader = null;
        }

        private function loseConnection() : void
        {
            view = null;
            generation = "";
            busy = false;
            if (isFrontMenu()) refreshMenu();
            else heldBack = true;
        }

        private function current() : Boolean
        {
            return acceptable(view);
        }

        private function isFrontMenu() : Boolean
        {
            if (!attached || isSubMenu || UIMenu.getActiveMenu() !== this) return false;
            var shell:ITAGameShell = TAGameShellInstance.get();
            return shell != null && !shell.getIsModalOpen() && !shell.modalManager.hasOpenScreens() &&
                shell.screenManager.getTopScreen() === parent;
        }

        private function acceptable(incoming:Object) : Boolean
        {
            if (incoming == null || incoming.active !== true || incoming.protocol !== 1 ||
                incoming.surface !== SURFACE || incoming.session !== SESSION ||
                !(incoming.generation is String) || !/^[1-9][0-9]{0,19}$/.test(String(incoming.generation)) ||
                !(incoming.controls is Array) || incoming.controls.length > 24) return false;
            var age:Number = new Date().time / 1000 - Number(incoming.published_at);
            if (!(isFinite(age) && age >= -1 && age <= 5)) return false;
            if (!(incoming.title is String) || incoming.title.length == 0 || incoming.title.length > 80) return false;
            if (!(incoming.body is String) || incoming.body.length == 0 || utf8Size(String(incoming.body)) > BODY_UTF8_MAX) return false;
            for each (var item:Object in incoming.controls)
                if (!usable(item)) return false;
            return true;
        }

        private function usable(item:Object) : Boolean
        {
            if (item == null || !(item.enabled is Boolean) || !(item.id is String) || item.id.length == 0 || item.id.length > 80 ||
                !(item.label is String) || item.label.length == 0 || item.label.length > 80 ||
                !(item.reason is String) || item.reason.length > 240 ||
                !(item.revision is String) || !/^[0-9]{1,20}$/.test(String(item.revision))) return false;
            return item.stock == null || item.stock === "" || item.stock === "resume" || item.stock === "options";
        }

        private function utf8Size(value:String) : int
        {
            var bytes:ByteArray = new ByteArray();
            bytes.writeUTFBytes(value);
            return bytes.length;
        }
    }
}

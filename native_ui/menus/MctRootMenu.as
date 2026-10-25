package menus
{
    import flash.events.Event;
    import com.adobe.serialization.json.JSON;
    import flash.display.InteractiveObject;
    import flash.events.IOErrorEvent;
    import flash.events.SecurityErrorEvent;
    import flash.events.TimerEvent;
    import flash.net.URLLoader;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import flash.utils.Timer;
    import flash.utils.getTimer;
    import projectx.core.UIMenu;
    import projectx.core.UIScreen;
    import scaleform.clik.controls.Button;
    import scaleform.clik.core.UIComponent;
    import scaleform.clik.managers.FocusHandler;
    import scaleform.gfx.TextFieldEx;
    import tagame.api.DevUtil;
    import tagame.api.MenuSequence;
    import tagame.api.Shell;
    import tagame.api.System;
    import tagame.constants.MenuName;
    import tagame.core.ITAGameShell;
    import tagame.core.TAGameShellInstance;
    import tagame.menus.BranchingMenu;

    // Authored mod source, compiled against private external game declarations.
    // The build replaces only these two literals for the owned session.
    // URLLoader file access and the DevUtil hook still require game validation.
    public class MctRootMenu extends BranchingMenu
    {
        private static const VIEW_URL:String = "__MCT_VIEW_URL__";
        private static const SESSION:String = "__MCT_SESSION__";
        private static const PAGE_SIZE:int = 7;
        private var timer:Timer;
        private var loader:URLLoader;
        private var loadStarted:int;
        private var view:Object;
        private var generation:String = "";
        private var page:int = 0;
        private var focusId:String = "";
        private var details:TextField;
        private var attached:Boolean = false;
        private var busy:Boolean = false;
        private var busyStarted:int = 0;
        private var resetFocus:Boolean = false;
        private var lastHello:int = -1000;

        public function MctRootMenu()
        {
            super();
            details = new TextField();
            details.multiline = true;
            details.wordWrap = true;
            details.autoSize = TextFieldAutoSize.NONE;
            details.selectable = false;
            details.mouseEnabled = false;
            details.width = 620;
            details.height = 530;
            details.defaultTextFormat = new TextFormat("Arial", 20, 0xFFFFFF);
            addChild(details);
        }

        override protected function configUI() : void
        {
            m_defaultControlClassName = "BasicThickExtendableMenuButtonWithIcon";
            m_controlWidth = 0;
            super.configUI();
            m_controlSpacing = 35;
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
            // A normal Garage transition removes the root from the display
            // while retaining it in the menu stack for Back navigation.
            if (timer != null && !UIMenu.isMenuInStack(menuName)) timer.stop();
            closeLoader();
            super.handleRemovedFromStage(event);
        }

        override public function onAddedToStack() : void
        {
            super.onAddedToStack();
            MenuSequence.PushMenuSequence("MainMenu", "RootMenu");
        }

        override public function onRemovedFromStack() : void
        {
            super.onRemovedFromStack();
            MenuSequence.PopMenuSequence("RootMenu");
            if (timer != null) timer.stop();
            closeLoader();
        }

        override protected function handleBackEvent(event:Event = null) : Boolean
        {
            if (!isFrontMenu()) return false;
            if (!current()) return true;
            for each (var item:Object in view.controls)
            {
                if (item.id == "nav.back")
                {
                    choose(item);
                    return true;
                }
            }
            // Root stays in this offline menu; Exit is an explicit choice.
            return true;
        }

        override protected function refreshMenu() : void
        {
            if (resetFocus) focusId = "";
            else if (currentFocus is UIComponent && UIComponent(currentFocus).enabled && contains(currentFocus))
                focusId = currentFocus.name;
            resetFocus = false;
            clearMenuFocus();
            super.refreshMenu();

            var selected:UIComponent = null;
            var firstSafe:UIComponent = null;
            var back:UIComponent = null;
            var recoveryConfirmation:Boolean = false;
            for each (var control:UIComponent in m_controls)
            {
                if (control.name == "career.recover.confirm") recoveryConfirmation = true;
                if (!control.enabled) continue;
                if (control.name != "session.exit" && control.name != "mct.exit" && control.name != "career.recover.confirm" && firstSafe == null)
                    firstSafe = control;
                if (control.name == "nav.back") back = control;
                if (focusId != "" && control.name == focusId) selected = control;
            }
            if (selected == null)
                selected = recoveryConfirmation ? back : firstSafe;
            // DynamicMenu restores by callback, shared by every career button.
            // Replace that incidental choice with the validated control identity.
            clearMenuFocus();
            if (selected != null) currentFocus = selected;
            layoutDetails();
            if (selected == null || !isFrontMenu()) return;
            selected.validateNow();
            if (selected.stage != null && selected.tabEnabled && selected.enabled && m_controls.indexOf(selected) >= 0)
                FocusHandler.getInstance().setFocus(selected);
        }

        private function clearMenuFocus() : void
        {
            if (m_currentFocus != null)
                m_currentFocus.removeEventListener(Event.TAB_ENABLED_CHANGE, invalidateFocus);
            // UIMenu's currentFocus setter deliberately ignores null. Clear
            // protected state and stale callback restoration before rebuilding.
            m_currentFocus = null;
            m_currentFocusCallbackData = null;
        }

        private function sameControlIds(left:Object, right:Object) : Boolean
        {
            if (left == null || right == null || left.controls.length != right.controls.length) return false;
            for (var i:int = 0; i < left.controls.length; ++i)
                if (left.controls[i].id !== right.controls[i].id) return false;
            return true;
        }

        override protected function handleStageResized(event:Event = null) : void
        {
            super.handleStageResized(event);
            layoutDetails();
        }

        private function layoutDetails() : void
        {
            if (details == null) return;
            details.x = Math.max(380, m_controlContainer.width + 40);
            details.width = Math.max(260, UIScreen.ContentStageWidth - details.x - 40);
            details.height = Math.min(530, Math.max(120, UIScreen.ContentStageHeight - 160));
            details.y = Math.max(40, Math.min(m_controlContainer.y, UIScreen.ContentStageHeight - details.height - 120));
            fitDetails();
        }

        private function fitDetails() : void
        {
            var copy:String = details.text;
            var format:TextFormat = details.defaultTextFormat;
            if (format == null) format = new TextFormat("Arial", 20, 0xFFFFFF);
            // The native button format may reserve space for its icon. The
            // separate body field uses the full bounded text rectangle.
            format.leftMargin = 0;
            format.rightMargin = 0;
            format.indent = 0;
            format.blockIndent = 0;
            format.align = "left";
            details.wordWrap = true;
            details.autoSize = TextFieldAutoSize.NONE;
            for (var size:int = 20; size >= 14; --size)
            {
                format.size = size;
                details.defaultTextFormat = format;
                details.text = copy;
                details.setTextFormat(format);
                if (details.textHeight <= details.height - 4 && details.textWidth <= details.width - 4) break;
            }
            TextFieldEx.setTextAutoSize(details, TextFieldEx.TEXTAUTOSZ_SHRINK);
        }

        override protected function getDirectionalFocus(direction:String) : InteractiveObject
        {
            // BranchingMenu otherwise sends RIGHT to the shell matchmaking
            // panel. Keep directional navigation inside the career controls.
            return null;
        }

        override protected function generateControls() : void
        {
            if (!current())
            {
                addChoice({id:"waiting", label:"MY CAREER", reason:"Waiting for the offline career service", enabled:false});
                var exitButton:UIComponent = createControl({name:"mct.exit", label:"QUIT MY CAREER", descLabel:"Close Rocket League"}, Shell.ExitGame);
                if (exitButton != null) exitButton.validateNow();
                setDetails("My Career", "Connecting to your offline career. Your saved progress stays on this computer.");
                return;
            }
            var count:int = view.controls.length;
            if (page * PAGE_SIZE >= count) page = 0;
            var end:int = Math.min(count, (page + 1) * PAGE_SIZE);
            for (var i:int = page * PAGE_SIZE; i < end; ++i) addChoice(view.controls[i]);
            if (page > 0) pageButton("PREVIOUS", -1);
            if (end < count) pageButton("MORE", 1);
            setDetails(String(view.title), String(view.body));
        }

        private function addChoice(item:Object) : void
        {
            var button:UIComponent = createControl({name:String(item.id), label:String(item.label),
                descLabel:String(item.reason), enabled:item.enabled === true && !busy}, choose, [item]);
            if (button == null) return;
            button.validateNow();
            // Reuse the actual native button's font when the timeline supplies it.
            var nativeButton:Button = button as Button;
            if (nativeButton != null && nativeButton.textField != null && details != null)
            {
                var format:TextFormat = nativeButton.textField.defaultTextFormat;
                format.size = 20;
                details.defaultTextFormat = format;
            }
        }

        private function pageButton(label:String, direction:int) : void
        {
            var button:UIComponent = createControl({name:direction < 0 ? "mct.page.previous" : "mct.page.more", label:label, descLabel:"More choices", enabled:!busy}, turnPage, [direction]);
            if (button != null) button.validateNow();
        }

        private function turnPage(direction:int) : void
        {
            if (!isFrontMenu() || !current() || busy) return;
            page = Math.max(0, page + direction);
            resetFocus = true;
            refreshMenu();
        }

        private function setDetails(title:String, body:String) : void
        {
            if (details == null) return;
            details.text = title + "\n\n" + body;
            layoutDetails();
        }

        private function current() : Boolean
        {
            return validView(view);
        }

        private function isFrontMenu() : Boolean
        {
            if (!attached || isSubMenu || UIMenu.getActiveMenu() !== this) return false;
            var shell:ITAGameShell = TAGameShellInstance.get();
            return shell != null && !shell.getIsModalOpen() && !shell.modalManager.hasOpenScreens() &&
                shell.screenManager.getTopScreen() === parent;
        }

        private function validView(candidate:Object) : Boolean
        {
            if (candidate == null || candidate.active !== true || candidate.protocol !== 1 ||
                candidate.session !== SESSION || !(candidate.generation is String) ||
                !/^[1-9][0-9]{0,19}$/.test(candidate.generation)) return false;
            var age:Number = new Date().time / 1000 - Number(candidate.published_at);
            return isFinite(age) && age >= -1 && age <= 5 && candidate.controls is Array;
        }

        private function choose(item:Object) : void
        {
            if (!isFrontMenu() || !current() || busy || item.enabled !== true) return;
            var present:Boolean = false;
            for each (var candidate:Object in view.controls)
                if (candidate === item) present = true;
            if (!present) return;
            if (item.stock === "garage")
            {
                if (TAGameShellInstance.get() == null) return;
                UIMenu.openMenu(MenuName.GARAGE_MAIN, parent, true);
                return;
            }
            if (item.stock === "options")
            {
                var shell:ITAGameShell = TAGameShellInstance.get();
                if (shell != null && shell.screenManager.isScreenOpen("ChallengesPrimeMenu")) return;
                System.SetSharedUIState("Options");
                return;
            }
            busy = true;
            busyStarted = getTimer();
            DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1, session:SESSION,
                generation:generation, revision:String(item.revision), control:String(item.id)}));
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
                if (incoming == null || !(incoming.controls is Array) || incoming.controls.length > 24)
                    throw new Error("Invalid menu");
                for each (var item:Object in incoming.controls)
                    if (!(item.id is String) || !(item.label is String) || item.label.length > 80 ||
                        !(item.reason is String) || item.reason.length > 240 || !(item.revision is String))
                        throw new Error("Invalid control");
                if (!validView(incoming)) { loseConnection(); return; }
                if (getTimer() - lastHello >= 1000)
                {
                    DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1, session:SESSION,
                        surface:"frontend", generation:String(incoming.generation), event:"ready"}));
                    lastHello = getTimer();
                }
                if (!isFrontMenu())
                {
                    // Continue the liveness handshake in stock Garage/Options
                    // without rebuilding controls or reclaiming their focus.
                    view = incoming;
                    generation = "";
                    return;
                }
                var next:String = incoming.generation;
                if (next != generation)
                {
                    if (view == null || incoming.title !== view.title || !sameControlIds(view, incoming))
                    {
                        page = 0;
                        resetFocus = true;
                    }
                    view = incoming;
                    generation = next;
                    busy = false;
                    refreshMenu();
                }
                else
                {
                    // Keep the control objects captured by visible callbacks.
                    // The host advances generation whenever a binding changes.
                    view.published_at = incoming.published_at;
                    if (busy && getTimer() - busyStarted >= 2000)
                    {
                        // The host rejects any repeated accepted generation.
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
            if (view == null && generation == "") return;
            view = null;
            generation = "";
            busy = false;
            lastHello = -1000;
            if (isFrontMenu()) refreshMenu();
        }
    }
}

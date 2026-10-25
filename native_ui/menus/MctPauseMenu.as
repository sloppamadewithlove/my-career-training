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
    import scaleform.clik.constants.InputValue;
    import scaleform.clik.controls.Button;
    import scaleform.clik.core.UIComponent;
    import scaleform.clik.events.InputEvent;
    import scaleform.clik.managers.FocusHandler;
    import scaleform.gfx.TextFieldEx;
    import tagame.api.DevUtil;
    import tagame.api.Shell;
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
        private var highestGeneration:String = "";
        private var consumedIntent:String = "";
        private var consumedActivity:String = "";
        private var consumedFixture:String = "";
        private var consumedGeneration:String = "";
        private var consumeSends:int = 0;
        private var lastConsume:int = 0;
        private var navigationIssued:Boolean = false;
        private var returnRequestGeneration:String = "";
        private var returnRequestStarted:int = 0;
        private var returnRequestId:String = "";
        private var returnRequestRevision:String = "";
        private var suppressHoldFocus:Boolean = false;

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
            clearConsumption();
            returnRequestGeneration = "";
            suppressHoldFocus = false;
            removeEventListener(Event.RENDER, validateFocus);
            removeEventListener(Event.ENTER_FRAME, validateFocus);
            closeLoader();
            if (timer != null && !UIMenu.isMenuInStack(menuName)) timer.stop();
            super.handleRemovedFromStage(event);
        }

        override public function close(transition:Boolean = true) : void
        {
            // Keep the current movie available while an accepted Return drains.
            // The fixed typed exit is allowed to perform its stock cleanup.
            if (!navigationIssued && isFrontMenu() && returnLocked()) return;
            super.close(transition);
        }

        override protected function handleInput(event:InputEvent) : void
        {
            if (suppressHoldFocus && returnLocked() && isFrontMenu() &&
                event != null && event.details != null && event.details.value == InputValue.KEY_DOWN &&
                (event.details.navEquivalent == NavigationCode.UP || event.details.navEquivalent == NavigationCode.DOWN))
            {
                // Quit remains reachable deliberately, but an Enter carried
                // over from Leave match must not select it automatically.
                for each (var recovery:UIComponent in m_buttons)
                {
                    if (recovery == null || !recovery.enabled) continue;
                    suppressHoldFocus = false;
                    currentFocus = recovery;
                    syncFocus();
                    event.handled = true;
                    event.preventDefault();
                    return;
                }
            }
            if (suppressHoldFocus && returnLocked() && isFrontMenu())
            {
                // No safe default control exists during cleanup. A carried
                // Enter/A or held direction must not activate recovery Quit.
                event.handled = true;
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }
            if (isFrontMenu() && returnLocked() && event != null && event.details != null &&
                (event.details.navEquivalent == NavigationCode.ESCAPE ||
                 event.details.navEquivalent == NavigationCode.GAMEPAD_B ||
                 event.details.navEquivalent == NavigationCode.GAMEPAD_START))
            {
                event.handled = true;
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }
            // Vertical authored buttons keep focus. RIGHT is the inherited
            // Friends handoff, so it is not forwarded. Escape and Start still
            // reach the stock resume close when no committed Return is held.
            if (event != null && event.details != null && event.details.navEquivalent == NavigationCode.RIGHT)
            {
                event.handled = true;
                return;
            }
            if (navigationIssued && !returnLocked() && isFrontMenu() && event != null && event.details != null &&
                (event.details.navEquivalent == NavigationCode.ESCAPE ||
                 event.details.navEquivalent == NavigationCode.GAMEPAD_B ||
                 event.details.navEquivalent == NavigationCode.GAMEPAD_START)) m_bExitingMatch = false;
            super.handleInput(event);
        }

        override protected function refreshMenu() : void
        {
            super.refreshMenu();
            layoutDetails();
            x = UIScreen.ContentStageWidth * 0.5;
            y = Math.max(0, (UIScreen.ContentStageHeight - height) * 0.5);
            syncFocus();
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
            showFitted(current() ? String(view.title) + "\n\n" + String(view.body) : "Paused\n\nWaiting for My Career. Press Escape to resume.");
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
            suppressHoldFocus = false;
            var resumeButton:Button = null;
            var cancelButton:Button = null;
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
                    enabled:item.enabled === true && !(navigationIssued && item.return_commit === true) &&
                    ((item.stock === "resume" || item.stock === "options") ? !returnLocked() : (!busy && !(returnLocked() && item.return_commit === true)))}, choose, [item]);
                made.validateNow();
                if (item.stock === "resume") resumeButton = made;
                if (item.id === "match.cancel_return") cancelButton = made;
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
            if (returnLocked())
            {
                holdWithoutFocus();
                return;
            }
            if (cancelButton != null && cancelButton.enabled)
            {
                currentFocus = cancelButton;
                return;
            }
            if (resumeButton != null && resumeButton.enabled)
            {
                currentFocus = resumeButton;
                return;
            }
            for each (var open:Button in m_buttons)
            {
                if (open.enabled)
                {
                    currentFocus = open;
                    return;
                }
            }
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
                if (returnLocked()) return;
                // A failed exit may leave its stock flag set. An explicit
                // user Resume is recovery, not another navigation attempt.
                if (navigationIssued) m_bExitingMatch = false;
                close();
                return;
            }
            if (item.stock === "options")
            {
                if (returnLocked()) return;
                if (m_shell != null) openOptionsMenu();
                return;
            }
            if (item.stock != null && item.stock !== "") return;
            if (busy || (item.return_commit === true && (navigationIssued || returnLocked()))) return;
            busy = true;
            busyStarted = getTimer();
            if (item.return_commit === true)
            {
                // Cover only the click-to-host-view gap. Rejection, lost input,
                // or stale data must not trap the player in a local-only lock.
                returnRequestGeneration = generation;
                returnRequestStarted = busyStarted;
                returnRequestId = String(item.id);
                returnRequestRevision = String(item.revision);
            }
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
                var next:String = String(incoming.generation);
                if (highestGeneration != "" && compareGeneration(next, highestGeneration) < 0) return;
                highestGeneration = next;
                updateReturnRequest(incoming, next);
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
                processNavigation();
            }
            catch (error:Error) { loseConnection(); }
        }

        private function returnLocked() : Boolean
        {
            if (!current()) return false;
            if (view.return_hold === true) return true;
            return returnRequestGeneration != "" && getTimer() - returnRequestStarted < 2000;
        }

        private function updateReturnRequest(incoming:Object, next:String) : void
        {
            if (returnRequestGeneration == "") return;
            if (incoming.return_pending === true || getTimer() - returnRequestStarted >= 2000)
            {
                // Accepted host hold takes over, or explicit host recovery
                // releases it. Neither state relies on this provisional latch.
                returnRequestGeneration = "";
                return;
            }
            if (compareGeneration(next, returnRequestGeneration) <= 0) return;
            for each (var item:Object in incoming.controls)
            {
                if (item.id === returnRequestId && item.revision === returnRequestRevision &&
                    item.return_commit === true) return;
            }
            // A newer view replaced the clicked binding without accepting it.
            // An unrelated body refresh with the same binding is not rejection.
            returnRequestGeneration = "";
        }

        private function holdWithoutFocus() : void
        {
            suppressHoldFocus = true;
            if (m_currentFocus != null)
                m_currentFocus.removeEventListener(Event.TAB_ENABLED_CHANGE, invalidateFocus);
            // The inherited setter deliberately ignores null.
            m_currentFocus = null;
        }

        override protected function validateFocus(event:Event = null) : void
        {
            var control:UIComponent = currentFocus as UIComponent;
            if (suppressHoldFocus && returnLocked() &&
                (control == null || !control.enabled || control.stage == null || !contains(control)))
            {
                removeEventListener(Event.RENDER, validateFocus);
                removeEventListener(Event.ENTER_FRAME, validateFocus);
                if (isFrontMenu()) FocusHandler.getInstance().setFocus(this);
                return;
            }
            suppressHoldFocus = false;
            super.validateFocus(event);
        }

        private function syncFocus() : void
        {
            if (!isFrontMenu()) return;
            if (suppressHoldFocus && returnLocked() && currentFocus == null)
            {
                FocusHandler.getInstance().setFocus(this);
                return;
            }
            if (currentFocus == null) return;
            var control:UIComponent = currentFocus as UIComponent;
            if (control == null || !control.enabled) return;
            control.validateNow();
            if (control.stage == null || !control.tabEnabled) return;
            // currentFocus alone defers to the stock interaction-mode check.
            // Sync this rebuilt front menu so Enter works before an arrow key.
            FocusHandler.getInstance().setFocus(control);
        }

        // A log callback has no return value. Consumption requests never exit;
        // only a later host execute view can grant this movie the fixed call.
        private function processNavigation() : void
        {
            if (navigationIssued || !isFrontMenu() || !current()) return;
            var navigation:Object = view.navigation;
            if (navigation == null)
            {
                clearConsumption();
                return;
            }
            if (consumedIntent != String(navigation.intent) ||
                consumedActivity != String(navigation.activity) ||
                consumedFixture != String(navigation.fixture)) clearConsumption();
            if (navigation.phase === "authorize")
            {
                if (consumedGeneration != generation)
                {
                    consumedIntent = String(navigation.intent);
                    consumedActivity = String(navigation.activity);
                    consumedFixture = String(navigation.fixture);
                    consumedGeneration = generation;
                    consumeSends = 0;
                }
                // Bounded retransmission handles a dropped void log callback.
                // The payload and local grant stay identical; exit is never retried.
                if (consumeSends >= 3 || (consumeSends > 0 && getTimer() - lastConsume < 1000)) return;
                consumeSends++;
                lastConsume = getTimer();
                DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1,
                    event:"return_navigation_consumed", session:SESSION, surface:SURFACE,
                    generation:consumedGeneration, intent:consumedIntent,
                    activity:consumedActivity, fixture:consumedFixture}));
                return;
            }
            if (consumedGeneration == "" || consumeSends == 0 ||
                navigation.consumed_generation !== consumedGeneration ||
                compareGeneration(generation, consumedGeneration) <= 0) return;
            // Latch before logging or calling. Re-entrant callbacks, polling, and
            // stale-view recovery cannot issue a second exit from this movie.
            navigationIssued = true;
            busy = true;
            DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1,
                event:"return_navigation_issued", session:SESSION, surface:SURFACE,
                generation:generation, intent:consumedIntent, activity:consumedActivity,
                fixture:consumedFixture, consumed_generation:consumedGeneration}));
            if (!isFrontMenu() || !current()) return;
            m_bExitingMatch = true;
            Shell.ExitToMainMenu();
        }

        private function clearConsumption() : void
        {
            consumedIntent = "";
            consumedActivity = "";
            consumedFixture = "";
            consumedGeneration = "";
            consumeSends = 0;
            lastConsume = 0;
        }

        private function validNavigation(navigation:Object) : Boolean
        {
            if (navigation == null) return true;
            var keys:int = 0;
            for (var key:String in navigation)
            {
                if (key != "phase" && key != "intent" && key != "activity" &&
                    key != "fixture" && key != "consumed_generation") return false;
                keys++;
            }
            if (!(navigation.intent is String) || !/^[0-9a-f]{32}$/.test(String(navigation.intent)) ||
                !(navigation.activity is String) || navigation.activity.length == 0 || navigation.activity.length > 128 ||
                !(navigation.fixture is String) || navigation.fixture.length > 128) return false;
            if (navigation.phase === "authorize") return keys == 4 && !navigation.hasOwnProperty("consumed_generation");
            return navigation.phase === "execute" && keys == 5 &&
                navigation.consumed_generation is String &&
                /^[1-9][0-9]{0,19}$/.test(String(navigation.consumed_generation));
        }

        private function compareGeneration(left:String, right:String) : int
        {
            if (left.length != right.length) return left.length < right.length ? -1 : 1;
            if (left == right) return 0;
            return left < right ? -1 : 1;
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
            // Keep consumption during a temporary stale poll. No effect can run
            // until a fresh view arrives; unloading clears the grant separately.
            view = null;
            generation = "";
            returnRequestGeneration = "";
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
                !(incoming.controls is Array) || incoming.controls.length > 24 ||
                !(incoming.return_pending is Boolean) || !(incoming.return_hold is Boolean) ||
                (incoming.return_hold === true && incoming.return_pending !== true)) return false;
            var age:Number = new Date().time / 1000 - Number(incoming.published_at);
            if (!(isFinite(age) && age >= -1 && age <= 5)) return false;
            if (!(incoming.title is String) || incoming.title.length == 0 || incoming.title.length > 80) return false;
            if (!(incoming.body is String) || incoming.body.length == 0 || utf8Size(String(incoming.body)) > BODY_UTF8_MAX) return false;
            for each (var item:Object in incoming.controls)
                if (!usable(item)) return false;
            return validNavigation(incoming.navigation) &&
                (incoming.navigation == null || incoming.return_pending === true);
        }

        private function usable(item:Object) : Boolean
        {
            if (item == null || !(item.return_commit is Boolean) || !(item.enabled is Boolean) || !(item.id is String) || item.id.length == 0 || item.id.length > 80 ||
                !(item.label is String) || item.label.length == 0 || item.label.length > 80 ||
                !(item.reason is String) || item.reason.length > 240 ||
                !(item.revision is String) || !/^[0-9]{1,20}$/.test(String(item.revision))) return false;
            if (item.return_commit === true && item.stock != null && item.stock !== "") return false;
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

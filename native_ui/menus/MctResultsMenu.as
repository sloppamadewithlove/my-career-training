package menus
{
    import com.adobe.serialization.json.JSON;
    import flash.display.InteractiveObject;
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
    import scaleform.gfx.TextFieldEx;
    import scaleform.clik.controls.Button;
    import scaleform.clik.core.UIComponent;
    import scaleform.clik.events.InputEvent;
    import scaleform.clik.managers.FocusHandler;
    import tagame.api.DevUtil;
    import tagame.api.LoadoutSets;
    import tagame.api.LoadoutSetsLoadoutSets;
    import tagame.api.LoadoutSetsLoadoutSetsRow;
    import tagame.api.Shell;
    import tagame.core.ITAGameShell;
    import tagame.core.TAGameShellInstance;

    // Authored results actions. The document screen still owns the scoreboard.
    // Removed ready and matchmaking controls are not created. Their callbacks
    // that would touch those buttons or open matchmaking are neutralized here.
    public class MctResultsMenu extends EndGameMenu
    {
        private static const VIEW_URL:String = "__MCT_VIEW_URL__";
        private static const SESSION:String = "__MCT_SESSION__";
        private static const SURFACE:String = "results";
        private static const BODY_UTF8_MAX:int = 1536;
        private static const PRESET_ROWS_MAX:int = 64;
        private static const PRESET_NAME_MAX:int = 40;
        private static const CONTROL_TOP_MIN:Number = 180;
        // Local Change Preset page. It is bound to one view generation and the
        // shown results.preset revision, and never sends a service command.
        private var presetOpen:Boolean = false;
        private var presetBinding:String = "";
        private var presetIndex:int = -1;
        private var presetSignature:String = "";
        // navEquivalent of a local Back press. Its repeats and release are
        // consumed after the page changes, so the inherited handler never sees them.
        private var localBackKey:String = "";
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

        public function MctResultsMenu()
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
            closePresetState();
            localBackKey = "";
            returnRequestGeneration = "";
            suppressHoldFocus = false;
            removeEventListener(Event.RENDER, validateFocus);
            removeEventListener(Event.ENTER_FRAME, validateFocus);
            closeLoader();
            if (timer != null && !UIMenu.isMenuInStack(menuName)) timer.stop();
            super.handleRemovedFromStage(event);
        }

        override protected function refreshMenu() : void
        {
            super.refreshMenu();
            fitControls();
            layoutDetails();
            syncFocus();
        }

        override protected function handleStageResized(event:Event = null) : void
        {
            super.handleStageResized(event);
            fitControls();
            layoutDetails();
        }

        // The stock countdown advertises an online-style next match. Keep it
        // hidden; the game timer itself is untouched.
        override protected function onTimeToNextMatchChanged() : void
        {
            if (nextMatchCountdown != null) nextMatchCountdown.visible = false;
        }

        // Longer local pages (up to eight controls) must stay on screen. Move
        // the left control column up only when its bottom would pass the stage
        // margin; the centered scoreboard is not touched.
        private function fitControls() : void
        {
            if (m_controlContainer == null || m_controls.length == 0) return;
            var spacing:Number = m_controlSpacing > 0 ? m_controlSpacing : 33;
            var bottom:Number = UIScreen.ContentStageHeight - 24 - m_controls.length * spacing;
            if (m_controlContainer.y > bottom) m_controlContainer.y = Math.max(CONTROL_TOP_MIN, bottom);
        }

        // Live bounds: left menu column only, clear of the centered scoreboard.
        // The results screen already treats x 0..260 as that column. This field
        // uses the stock control container x (10) and control width (240), and
        // never extends past x 250. It starts at y 36 and stops 96px above the
        // control container so the stock vote row and next-match countdown stay
        // clear. If that gap is under 48px, the field sits 8px below the column,
        // at most 120px tall, and at least 24px above ContentStageHeight.
        // Stage resize and every control refresh repeat this. Scoreboard
        // position stays on the document screen. Wrapped title and body stay
        // inside that rectangle: 20px, then smaller by 1px down to 10px while
        // textHeight exceeds it, then TextFieldEx shrink.
        private function layoutDetails() : void
        {
            if (details == null || m_controlContainer == null) return;
            var columnW:Number = m_controlWidth > 0 ? m_controlWidth : 240;
            if (columnW > 240) columnW = 240;
            details.x = m_controlContainer.x;
            details.width = columnW;
            if (m_controls.length > 0)
            {
                var sample:Button = m_controls[0] as Button;
                if (sample != null && sample.textField != null)
                {
                    var format:TextFormat = sample.textField.defaultTextFormat;
                    format.size = 20;
                    format.color = 0xFFFFFF;
                    details.defaultTextFormat = format;
                }
            }
            var limit:Number = m_controlContainer.y - 96;
            if (limit < 84)
            {
                details.y = m_controlContainer.y + m_controls.length * m_controlSpacing + 8;
                details.height = Math.max(36, Math.min(120, UIScreen.ContentStageHeight - details.y - 24));
            }
            else
            {
                details.y = 36;
                details.height = limit - 36;
            }
            showFitted(!current() ? "Results\n\nWaiting for the offline career service." :
                presetOpen ? presetCopy() : String(view.title) + "\n\n" + String(view.body));
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

        override protected function generateControls() : void
        {
            var focusName:String = currentFocus != null ? currentFocus.name : "";
            suppressHoldFocus = false;
            var made:UIComponent = null;
            if (!current())
            {
                ownControl(createControl({label:"RESULTS", enabled:false}, ignoreChoice));
                return;
            }
            if (presetOpen && !presetValid()) closePresetState();
            if (presetOpen) generatePresetControls();
            else
            {
                for each (var item:Object in view.controls)
                {
                    if (!usable(item)) continue;
                    made = createControl({name:String(item.id), label:String(item.label), desc:String(item.reason),
                        enabled:item.enabled === true && !(navigationIssued && item.return_commit === true) &&
                        (stockRoute(item) ? !returnLocked() && !(item.stock === "preset" && view.return_pending === true) :
                        (!busy && !(returnLocked() && item.return_commit === true)))}, choose, [item]);
                    ownControl(made);
                }
            }
            var fallback:UIComponent = null;
            var safe:UIComponent = null;
            for each (var entry:Object in m_controls)
            {
                var control:UIComponent = entry as UIComponent;
                if (control == null || !control.enabled) continue;
                if (focusName != "" && control.name == focusName)
                {
                    currentFocus = control;
                    return;
                }
                // A carried activation from Play Next Match or Change Preset
                // must land on Back, never on Start or Equip.
                if (control.name == "results.preview_back" || control.name == "mct.preset.back") safe = control;
                if (fallback == null) fallback = control;
            }
            if (returnLocked()) holdWithoutFocus();
            else if (safe != null) currentFocus = safe;
            else if (fallback != null) currentFocus = fallback;
        }

        private static function stockRoute(item:Object) : Boolean
        {
            return item.stock === "options" || item.stock === "settings" || item.stock === "preset";
        }

        private function generatePresetControls() : void
        {
            var rows:Array = presetRows();
            presetSignature = signatureOf(rows);
            if (presetIndex < 0 || presetIndex >= rows.length) presetIndex = equippedIndex(rows);
            if (presetIndex < 0 && rows.length > 0) presetIndex = 0;
            var selected:LoadoutSetsLoadoutSetsRow = presetIndex >= 0 ? rows[presetIndex] as LoadoutSetsLoadoutSetsRow : null;
            if (rows.length > 1)
            {
                ownControl(createControl({name:"mct.preset.prev", label:"Previous preset", desc:"", enabled:true},
                    choosePreset, ["prev"]));
                ownControl(createControl({name:"mct.preset.next", label:"Next preset", desc:"", enabled:true},
                    choosePreset, ["next"]));
            }
            if (selected != null)
            {
                var name:String = presetName(selected);
                ownControl(createControl({name:"mct.preset.equip",
                    label:(selected.bEquipped ? "Equipped: " : "Equip: ") + name, desc:"",
                    enabled:!selected.bEquipped}, choosePreset, ["equip"]));
            }
            ownControl(createControl({name:"mct.preset.back", label:"Back", desc:"", enabled:true}, choosePreset, ["back"]));
        }

        private function presetCopy() : String
        {
            var rows:Array = presetRows();
            if (rows.length == 0) return "Change Preset\n\nNo car presets are available.";
            var equipped:int = equippedIndex(rows);
            var index:int = presetIndex >= 0 && presetIndex < rows.length ? presetIndex : equipped;
            var copy:String = "Change Preset\n\nCurrent: " +
                (equipped >= 0 ? presetName(LoadoutSetsLoadoutSetsRow(rows[equipped])) : "None");
            if (index >= 0)
                copy += "\nSelected: " + presetName(LoadoutSetsLoadoutSetsRow(rows[index])) +
                    " (" + String(index + 1) + " of " + String(rows.length) + ")";
            return copy + "\n\nUses your saved local presets. Back returns to the results.";
        }

        private function presetRows() : Array
        {
            var all:Array = LoadoutSetsLoadoutSets.getAllRows();
            var rows:Array = [];
            if (all == null) return rows;
            for each (var entry:Object in all)
            {
                var row:LoadoutSetsLoadoutSetsRow = entry as LoadoutSetsLoadoutSetsRow;
                if (row != null) rows.push(row);
                if (rows.length >= PRESET_ROWS_MAX) break;
            }
            return rows;
        }

        private static function equippedIndex(rows:Array) : int
        {
            for (var index:int = 0; index < rows.length; index++)
                if (LoadoutSetsLoadoutSetsRow(rows[index]).bEquipped) return index;
            return -1;
        }

        private static function signatureOf(rows:Array) : String
        {
            var signature:String = String(rows.length);
            for each (var row:LoadoutSetsLoadoutSetsRow in rows)
                signature += "|" + String(row.RowIndex) + ":" + (row.bEquipped ? "1" : "0") + ":" + presetName(row);
            return signature;
        }

        private static function presetName(row:LoadoutSetsLoadoutSetsRow) : String
        {
            var name:String = row != null && row.Name != null ? String(row.Name) : "";
            if (name.length == 0) return "Preset";
            return name.length > PRESET_NAME_MAX ? name.substr(0, PRESET_NAME_MAX) : name;
        }

        private function presetControl() : Object
        {
            if (!current()) return null;
            for each (var item:Object in view.controls)
                if (item.id === "results.preset" && item.stock === "preset") return item;
            return null;
        }

        // Same owned view, generation and preset binding, no Return intent.
        private function presetValid() : Boolean
        {
            var item:Object = presetControl();
            return presetOpen && item != null && item.enabled === true && view.return_pending !== true &&
                !returnLocked() && !navigationIssued && String(view.generation) == generation &&
                presetBinding == generation + ":" + String(item.revision);
        }

        private function openPreset(item:Object) : void
        {
            if (!isFrontMenu() || view.return_pending === true || returnLocked() || navigationIssued) return;
            presetOpen = true;
            presetBinding = generation + ":" + String(item.revision);
            presetIndex = equippedIndex(presetRows());
            refreshMenu();
        }

        private function closePresetState() : void
        {
            presetOpen = false;
            presetBinding = "";
            presetIndex = -1;
            presetSignature = "";
        }

        private function choosePreset(action:String) : void
        {
            if (!isFrontMenu()) return;
            if (!presetValid())
            {
                closePresetState();
                refreshMenu();
                return;
            }
            var rows:Array = presetRows();
            if (action == "back")
            {
                closePresetState();
                refreshMenu();
                return;
            }
            // The table can change between the last draw and this activation.
            // Act only on the exact rows the player saw; otherwise redraw.
            if (signatureOf(rows) != presetSignature)
            {
                refreshMenu();
                return;
            }
            if (rows.length > 0 && action == "prev") presetIndex = (presetIndex + rows.length - 1) % rows.length;
            else if (rows.length > 0 && action == "next") presetIndex = (presetIndex + 1) % rows.length;
            else if (action == "equip" && presetIndex >= 0 && presetIndex < rows.length)
            {
                var row:LoadoutSetsLoadoutSetsRow = LoadoutSetsLoadoutSetsRow(rows[presetIndex]);
                if (!row.bEquipped) LoadoutSets.EquipPreset(row.RowIndex);
            }
            refreshMenu();
        }

        private function openSettings() : void
        {
            var shell:ITAGameShell = TAGameShellInstance.get();
            if (shell == null || shell.modalManager == null) return;
            shell.modalManager.openScreen("SettingsMenu");
        }

        override protected function getDirectionalFocus(direction:String) : InteractiveObject
        {
            return null;
        }

        private function ownControl(made:UIComponent) : void
        {
            if (made == null) return;
            made.focusFunction = null;
            made.validateNow();
        }

        override protected function handleReadyChanged() : void
        {
            if (m_readyButton == null) return;
        }

        override protected function checkForFTE() : void
        {
        }

        // The document can close without entering this menu's close method.
        // Expose only the existing bounded decision, never a second authority.
        public function shouldHoldScreenClose() : Boolean
        {
            return !navigationIssued && isFrontMenu() && returnLocked();
        }

        override public function close(transition:Boolean = true) : void
        {
            // Keep the current movie available while an accepted Return drains.
            // The fixed typed exit is allowed to perform its stock cleanup.
            if (shouldHoldScreenClose()) return;
            super.close(transition);
        }

        override protected function handleInput(event:InputEvent) : void
        {
            if (localBackKey != "" && event != null && event.details != null &&
                event.details.navEquivalent == localBackKey)
            {
                // Consume only; this never acts, so Return-lock handling below
                // keeps its precedence for every other input.
                if (event.details.value == InputValue.KEY_UP) localBackKey = "";
                event.handled = true;
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }
            if (suppressHoldFocus && returnLocked() && isFrontMenu() &&
                event != null && event.details != null && event.details.value == InputValue.KEY_DOWN &&
                (event.details.navEquivalent == NavigationCode.UP || event.details.navEquivalent == NavigationCode.DOWN))
            {
                // Quit remains reachable deliberately, but an Enter carried
                // over from Leave match must not select it automatically.
                for each (var recovery:UIComponent in m_controls)
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
            if (presetOpen && isFrontMenu() && event != null && event.details != null &&
                (event.details.navEquivalent == NavigationCode.ESCAPE ||
                 event.details.navEquivalent == NavigationCode.GAMEPAD_B))
            {
                event.handled = true;
                event.preventDefault();
                event.stopImmediatePropagation();
                if (event.details.value == InputValue.KEY_DOWN)
                {
                    localBackKey = event.details.navEquivalent;
                    closePresetState();
                    refreshMenu();
                }
                return;
            }
            if (!presetOpen && isFrontMenu() && current() && event != null && event.details != null &&
                (event.details.navEquivalent == NavigationCode.ESCAPE ||
                 event.details.navEquivalent == NavigationCode.GAMEPAD_B))
            {
                // Schedule and preview pages go Back locally; the inherited
                // results handler must not close the completed match screen.
                var backItem:Object = null;
                for each (var candidate:Object in view.controls)
                {
                    if ((candidate.id === "results.schedule_back" || candidate.id === "results.preview_back") &&
                        candidate.enabled === true && usable(candidate)) backItem = candidate;
                }
                if (backItem != null)
                {
                    event.handled = true;
                    event.preventDefault();
                    event.stopImmediatePropagation();
                    if (event.details.value == InputValue.KEY_DOWN)
                    {
                        localBackKey = event.details.navEquivalent;
                        choose(backItem);
                    }
                    return;
                }
            }
            if (event != null && event.details != null && event.details.navEquivalent == NavigationCode.GAMEPAD_Y)
            {
                event.handled = true;
                return;
            }
            super.handleInput(event);
        }

        private function ignoreChoice() : void
        {
        }

        private function choose(item:Object) : void
        {
            if (!isFrontMenu() || !current() || item == null || item.enabled !== true) return;
            var present:Boolean = false;
            for each (var candidate:Object in view.controls)
                if (candidate === item) present = true;
            if (!present || String(view.generation) != generation || presetOpen) return;
            if (stockRoute(item))
            {
                // Local game screens only; no service dispatch is sent.
                if (returnLocked()) return;
                if (item.stock === "options") openOptionsMenu();
                else if (item.stock === "settings") openSettings();
                else openPreset(item);
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
            if (presetOpen && isFrontMenu() && (!presetValid() || signatureOf(presetRows()) != presetSignature))
                refreshMenu();
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
                if (next != generation || incoming.return_pending === true) closePresetState();
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
            closePresetState();
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
            return item.stock == null || item.stock === "" || stockRoute(item);
        }

        private function utf8Size(value:String) : int
        {
            var bytes:ByteArray = new ByteArray();
            bytes.writeUTFBytes(value);
            return bytes.length;
        }
    }
}

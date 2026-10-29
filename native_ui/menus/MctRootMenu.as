package menus
{
    import flash.events.Event;
    import com.adobe.serialization.json.JSON;
    import flash.display.Graphics;
    import flash.display.Bitmap;
    import flash.display.Loader;
    import flash.utils.ByteArray;
    import flash.display.InteractiveObject;
    import flash.display.Sprite;
    import flash.events.IOErrorEvent;
    import flash.events.FocusEvent;
    import flash.events.KeyboardEvent;
    import flash.events.MouseEvent;
    import flash.events.SecurityErrorEvent;
    import flash.events.TimerEvent;
    import flash.net.URLLoader;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFieldType;
    import flash.text.TextFormat;
    import flash.utils.Timer;
    import flash.utils.getTimer;
    import flash.utils.setTimeout;
    import projectx.core.UIMenu;
    import projectx.core.UIScreen;
    import scaleform.clik.controls.Button;
    import scaleform.clik.core.UIComponent;
    import scaleform.clik.events.ButtonEvent;
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
        // Actual Gold Power Shots gameplay, cropped to 400x225; no generated art.
        private static const POWER_SHOTS_JPEG:String = "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";
        private var lessonPreview:Loader;
        private var lessonPreviewState:int = 0; // idle, loading, ready, unavailable
        private static const PAGE_SIZE:int = 7;
        private static const BROWSER_ROWS:int = 8;
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
        // One gesture, one action. A control callback runs only for the exact
        // control instance that received this gesture's press. Rebuilds caused
        // by that action wait until the dispatch has unwound, and no press can
        // arm until then, so a release or synthesized click cannot reach a
        // control created by the same gesture.
        private var armedControl:Object = null;
        private var armedController:uint = 0;
        private var armedButton:uint = 0;
        private var armedKeyboard:Boolean = false;
        private var gestureSpent:Boolean = false;
        private var refreshQueued:Boolean = false;
        private var gestureContainer:Object = null;
        private var selectedRowKey:String = "";
        private var browserLayer:Sprite;
        private var browserSearch:TextField;
        private var browserSearchHint:TextField;
        private var browserZone:String = "tabs";
        private var browserTabFocus:int = 0;
        private var browserToolFocus:int = 0;
        private var browserTop:int = 0;
        private var browserPendingMove:int = 0;
        private var browserSearchEditing:Boolean = false;
        private var browserSearchPending:Boolean = false;
        private var browserPendingQuery:String = "";
        private var browserSearchRetries:int = 0;

        public function MctRootMenu()
        {
            super();
            wireGesture();
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
            browserLayer = new Sprite();
            browserLayer.visible = false;
            addChild(browserLayer);
            lessonPreview = new Loader();
            lessonPreview.mouseEnabled = false;
            lessonPreview.mouseChildren = false;
            lessonPreview.visible = false;
            browserLayer.addChild(lessonPreview);
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
            stage.addEventListener(KeyboardEvent.KEY_DOWN, browserKey, false, 100, true);
            addEventListener(MouseEvent.MOUSE_WHEEL, browserWheel, false, 0, true);
            wireGesture();
            releaseGesture();
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
            if (stage != null) stage.removeEventListener(KeyboardEvent.KEY_DOWN, browserKey);
            removeEventListener(MouseEvent.MOUSE_WHEEL, browserWheel);
            // A normal Garage transition removes the root from the display
            // while retaining it in the menu stack for Back navigation.
            if (timer != null && !UIMenu.isMenuInStack(menuName)) timer.stop();
            closeLoader();
            releaseGesture();
            showBrowser(false);
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
            disarm();
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

        private function wireGesture() : void
        {
            if (m_controlContainer == null || gestureContainer === m_controlContainer) return;
            if (gestureContainer != null)
            {
                gestureContainer.removeEventListener(ButtonEvent.PRESS, armGesture, true);
                gestureContainer.removeEventListener(ButtonEvent.CLICK, gateGesture, true);
                gestureContainer.removeEventListener(ButtonEvent.RELEASE_OUTSIDE, abandonGesture, true);
            }
            // Capture phase on the container runs before the target-phase
            // listener that DynamicMenu.createControl puts on each control.
            m_controlContainer.addEventListener(ButtonEvent.PRESS, armGesture, true, 0, true);
            m_controlContainer.addEventListener(ButtonEvent.CLICK, gateGesture, true, 0, true);
            m_controlContainer.addEventListener(ButtonEvent.RELEASE_OUTSIDE, abandonGesture, true, 0, true);
            gestureContainer = m_controlContainer;
        }

        private function armGesture(event:ButtonEvent) : void
        {
            disarm();
            if (gestureSpent || event.isRepeat || m_controls.indexOf(event.target) < 0) return;
            armedControl = event.target;
            armedController = event.controllerIdx;
            armedButton = event.buttonIdx;
            armedKeyboard = event.isKeyboard;
        }

        private function gateGesture(event:ButtonEvent) : void
        {
            var control:Object = event.target;
            if (!gestureSpent && !event.isRepeat && ownsGesture(event) &&
                m_controls.indexOf(control) >= 0 && contains(control as UIComponent))
            {
                disarm();
                gestureSpent = true;
                addEventListener(Event.ENTER_FRAME, settleGesture, false, 0, true);
                return;
            }
            event.stopImmediatePropagation();
        }

        // An accepted action asks for a rebuild here instead of destroying the
        // controls inside the activating button's own click dispatch.
        private function queueRefresh() : void
        {
            if (!gestureSpent)
            {
                refreshMenu();
                return;
            }
            refreshQueued = true;
        }

        private function settleGesture(event:Event = null) : void
        {
            removeEventListener(Event.ENTER_FRAME, settleGesture);
            var rebuild:Boolean = refreshQueued;
            refreshQueued = false;
            disarm();
            gestureSpent = false;
            if (rebuild) refreshMenu();
        }

        // Stock RELEASE_OUTSIDE carries default source fields, so it can only
        // end a primary mouse press. A keyboard, controller, or other-device
        // press on the same control keeps its ownership.
        private function abandonGesture(event:ButtonEvent) : void
        {
            if (ownsGesture(event)) disarm();
        }

        private function ownsGesture(event:ButtonEvent) : Boolean
        {
            return armedControl != null && event.target === armedControl &&
                event.controllerIdx == armedController && event.buttonIdx == armedButton &&
                event.isKeyboard == armedKeyboard;
        }

        private function disarm() : void
        {
            armedControl = null;
            armedController = 0;
            armedButton = 0;
            armedKeyboard = false;
        }

        private function releaseGesture() : void
        {
            removeEventListener(Event.ENTER_FRAME, settleGesture);
            disarm();
            gestureSpent = false;
            refreshQueued = false;
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
            if (browserLayer != null && browserLayer.visible)
            {
                renderBrowser();
                return;
            }
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
                showBrowser(false);
                addChoice({id:"waiting", label:"MY CAREER", reason:"Waiting for the offline career service", enabled:false});
                var exitButton:UIComponent = createControl({name:"mct.exit", label:"QUIT MY CAREER", descLabel:"Close Rocket League"}, Shell.ExitGame);
                if (exitButton != null) exitButton.validateNow();
                setDetails("My Career", "Connecting to your offline career. Your saved progress stays on this computer.");
                return;
            }
            if (view.browser != null)
            {
                generateBrowser();
                return;
            }
            showBrowser(false);
            var count:int = view.controls.length;
            if (page * PAGE_SIZE >= count) page = 0;
            var end:int = Math.min(count, (page + 1) * PAGE_SIZE);
            for (var i:int = page * PAGE_SIZE; i < end; ++i) addChoice(view.controls[i]);
            if (page > 0) pageButton("PREVIOUS", -1);
            if (end < count) pageButton("MORE", 1);
            setDetails(String(view.title), String(view.body));
        }

        private function generateBrowser() : void
        {
            showBrowser(true);
            var tabs:Array = ["lessons", "workshop", "mods"];
            browserTabFocus = Math.max(0, tabs.indexOf(String(view.browser.tab)));
            normalizeBrowserSelection();
            renderBrowser();
        }

        private function browserCommand(op:String, value:String) : void
        {
            if (!isFrontMenu() || !current() || busy || view.browser == null) return;
            busy = true; busyStarted = getTimer();
            DevUtil.Log("MCT_NATIVE_UI_V1", com.adobe.serialization.json.JSON.encode({protocol:1, session:SESSION,
                surface:"frontend", generation:generation, revision:String(view.browser.revision),
                browser_op:op, value:value}));
        }

        private function browserKey(event:KeyboardEvent) : void
        {
            if (!isFrontMenu() || !current() || view.browser == null || event.ctrlKey || event.altKey) return;
            if (browserSearchEditing && stage != null && stage.focus === browserSearch)
            {
                if (event.keyCode == 13 || event.keyCode == 40 || event.keyCode == 9)
                {
                    browserSearchEditing = false;
                    browserZone = "rows";
                    stage.focus = null;
                    event.preventDefault();
                    event.stopImmediatePropagation();
                    renderBrowser();
                }
                else if (event.keyCode == 27)
                {
                    event.preventDefault();
                    event.stopImmediatePropagation();
                    browserSearch.text = "";
                    browserPendingQuery = "";
                    browserSearchPending = true;
                    browserSearchRetries = 0;
                    if (!busy && String(view.browser.query).length > 0)
                        browserCommand("search", "");
                }
                return;
            }
            if (busy) return;
            var handled:Boolean = true;
            if (event.keyCode == 37) browserLeft();
            else if (event.keyCode == 38) browserUp();
            else if (event.keyCode == 39) browserRight();
            else if (event.keyCode == 40) browserDown();
            else if (event.keyCode == 13 || event.keyCode == 32) activateBrowserFocus();
            else if (event.keyCode == 9) cycleBrowserFocus(event.shiftKey ? -1 : 1);
            else handled = false;
            if (handled)
            {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }

        private function browserWheel(event:MouseEvent) : void
        {
            if (!isFrontMenu() || !current() || view.browser == null || busy || event.delta == 0) return;
            browserZone = "rows";
            moveBrowserRow(event.delta > 0 ? -1 : 1);
            event.preventDefault();
            event.stopImmediatePropagation();
        }

        private function clearBrowserChildren() : void
        {
            // Keep the decoded preview alive across selection and Garage redraws.
            for (var i:int = browserLayer.numChildren - 1; i >= 0; --i)
                if (browserLayer.getChildAt(i) != lessonPreview) browserLayer.removeChildAt(i);
            lessonPreview.visible = false;
        }

        private function loadLessonPreview() : void
        {
            if (lessonPreviewState != 0) return;
            lessonPreviewState = 1;
            try
            {
                DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: start");
                lessonPreview.contentLoaderInfo.addEventListener(Event.COMPLETE, lessonPreviewLoaded, false, 0, true);
                lessonPreview.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, lessonPreviewFailed, false, 0, true);
                DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: listeners ready");
                var alphabet:String = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
                var bytes:ByteArray = new ByteArray();
                var value:uint = 0;
                var bits:int = 0;
                for (var i:int = 0; i < POWER_SHOTS_JPEG.length; ++i)
                {
                    var character:String = POWER_SHOTS_JPEG.charAt(i);
                    if (character == "=") break;
                    var digit:int = alphabet.indexOf(character);
                    if (digit < 0) throw new Error("Invalid embedded image");
                    value = (value << 6) | digit;
                    bits += 6;
                    if (bits >= 8)
                    {
                        bits -= 8;
                        bytes.writeByte((value >> bits) & 255);
                        value &= (1 << bits) - 1;
                    }
                }
                if (bytes.length > 16000) throw new Error("Embedded image exceeds limit");
                bytes.position = 0;
                DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: load " + bytes.length);
                lessonPreview.loadBytes(bytes);
                DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: load dispatched");
            }
            catch (error:Error) { lessonPreviewState = 3; lessonPreview.visible = false; DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: synchronous failure " + error.name); }
        }

        private function lessonPreviewLoaded(event:Event) : void
        {
            DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: complete");
            var bitmap:Bitmap = lessonPreview.content as Bitmap;
            if (bitmap == null || bitmap.bitmapData == null ||
                bitmap.bitmapData.width != 400 || bitmap.bitmapData.height != 225)
            {
                lessonPreviewFailed(null);
                return;
            }
            DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: dimensions valid");
            bitmap.smoothing = true;
            lessonPreviewState = 2;
            setTimeout(renderBrowser, 0);
        }

        private function lessonPreviewFailed(event:Event) : void
        {
            DevUtil.Log("MCT_THUMBNAIL", "MCT thumbnail: failed");
            lessonPreviewState = 3;
            lessonPreview.visible = false;
            setTimeout(renderBrowser, 0);
        }

        private function showBrowser(visible:Boolean) : void
        {
            if (browserLayer == null) return;
            browserLayer.visible = visible;
            if (m_controlContainer != null) m_controlContainer.visible = !visible;
            if (details != null) details.visible = !visible;
            if (visible)
            {
                setChildIndex(browserLayer, numChildren - 1);
                return;
            }
            browserSearch = null;
            browserSearchHint = null;
            browserSearchEditing = false;
            clearBrowserChildren();
            browserLayer.graphics.clear();
        }

        private function browserText(parent:Sprite, value:String, x:Number, y:Number, width:Number, height:Number,
                                     size:Number, color:uint = 0xFFFFFF, bold:Boolean = false,
                                     align:String = "left") : TextField
        {
            var field:TextField = new TextField();
            field.x = x; field.y = y; field.width = width; field.height = height;
            field.multiline = true; field.wordWrap = true; field.selectable = false; field.mouseEnabled = false;
            field.defaultTextFormat = new TextFormat("Arial", size, color, bold, null, null, null, null, align);
            field.text = displayText(value);
            parent.addChild(field);
            return field;
        }

        // The Scaleform text renderer only carries a small glyph set. Map the
        // punctuation that browser data may contain onto plain ASCII so titles
        // and instructions never fall back to missing-glyph squares.
        private function displayText(value:String) : String
        {
            if (value == null) return "";
            var out:String = value;
            out = out.split("\u2014").join("-");
            out = out.split("\u2013").join("-");
            out = out.split("\u2018").join("'");
            out = out.split("\u2019").join("'");
            out = out.split("\u201c").join("\"");
            out = out.split("\u201d").join("\"");
            out = out.split("\u2026").join("...");
            out = out.split("\u00b7").join("-");
            out = out.split("\u2605").join("*");
            out = out.split("\u2606").join("*");
            return out;
        }

        // Independent vector star. The path opens with its own moveTo so the
        // shared pen never connects this shape to whatever was drawn before it.
        private function drawStar(target:Graphics, cx:Number, cy:Number, outer:Number, inner:Number,
                                 filled:Boolean, color:uint) : void
        {
            target.lineStyle(2, color, 1);
            if (filled) target.beginFill(color, 1);
            for (var i:int = 0; i < 10; ++i)
            {
                var radius:Number = (i & 1) == 0 ? outer : inner;
                var angle:Number = -Math.PI / 2 + i * Math.PI / 5;
                var px:Number = cx + Math.cos(angle) * radius;
                var py:Number = cy + Math.sin(angle) * radius;
                if (i == 0) target.moveTo(px, py);
                else target.lineTo(px, py);
            }
            target.lineTo(cx, cy - outer);
            if (filled) target.endFill();
        }

        // Explicit closed paths avoid Scaleform's rounded-rectangle fill seams.
        private function drawBrowserRect(target:Graphics, x:Number, y:Number, width:Number, height:Number) : void
        {
            target.moveTo(x, y);
            target.lineTo(x + width, y);
            target.lineTo(x + width, y + height);
            target.lineTo(x, y + height);
            target.lineTo(x, y);
        }
        private function renderBrowser() : void
        {
            if (browserLayer == null || !browserLayer.visible || view == null || view.browser == null) return;
            var searchWasEditing:Boolean = browserSearchEditing && browserZone == "search";
            var searchBegin:int = browserSearch != null ? browserSearch.selectionBeginIndex : 0;
            var searchEnd:int = browserSearch != null ? browserSearch.selectionEndIndex : 0;
            if (browserSearch != null)
                browserSearch.removeEventListener(FocusEvent.FOCUS_OUT, browserSearchFocusOut);
            clearBrowserChildren();
            browserLayer.graphics.clear();
            browserSearch = null;
            browserSearchHint = null;

            var screenWidth:Number = Math.max(960, UIScreen.ContentStageWidth);
            var screenHeight:Number = Math.max(640, UIScreen.ContentStageHeight);
            var panelX:Number = Math.max(55, (screenWidth - 1600) / 2);
            var panelY:Number = Math.max(40, (screenHeight - 900) / 2);
            var panelWidth:Number = Math.min(1600, screenWidth - panelX * 2);
            var panelHeight:Number = Math.min(900, screenHeight - panelY * 2);
            var browser:Object = view.browser;
            var rows:Array = browser.rows as Array;
            var tools:Array = browser.tools as Array;
            var selected:Object = selectedBrowserRow();
            var g:* = browserLayer.graphics;

            g.beginFill(0x050B18, 0.82); g.moveTo(0, 0); drawBrowserRect(g, 0, 0, screenWidth, screenHeight); g.endFill();
            g.lineStyle(3, 0x2E8BFF, 1); g.beginFill(0x0B1A33, 0.97);
            g.moveTo(panelX, panelY);
            drawBrowserRect(g, panelX, panelY, panelWidth, panelHeight); g.endFill();

            browserText(browserLayer, "TRAINING", panelX + 30, panelY + 18, 280, 42, 28, 0xFFFFFF, true);
            browserText(browserLayer, "Offline library · selections stay on this computer", panelX + 250, panelY + 25,
                panelWidth - 280, 30, 13, 0x9FB4D4, false, "right");

            var tabs:Array = ["lessons", "workshop", "mods"];
            var labels:Array = ["LESSONS", "WORKSHOP", "MODS"];
            var tabY:Number = panelY + 68;
            var tabWidth:Number = Math.min(280, (panelWidth - 60) / 3);
            for (var t:int = 0; t < tabs.length; ++t)
            {
                var tab:Sprite = new Sprite();
                tab.name = "browser.tab." + tabs[t];
                tab.x = panelX + 30 + t * tabWidth; tab.y = tabY;
                tab.buttonMode = true; tab.mouseChildren = false;
                tab.graphics.lineStyle(browserZone == "tabs" && browserTabFocus == t ? 2 : 0,
                    browserZone == "tabs" && browserTabFocus == t ? 0xFFFFFF : 0x12305C, 1);
                tab.graphics.moveTo(0, 0);
                tab.graphics.beginFill(String(browser.tab) == tabs[t] ? 0x12305C : 0x0D2140, 1);
                drawBrowserRect(tab.graphics, 0, 0, tabWidth - 6, 46); tab.graphics.endFill();
                if (String(browser.tab) == tabs[t])
                {
                    tab.graphics.beginFill(0x2E8BFF, 1); tab.graphics.moveTo(0, 41);
                    drawBrowserRect(tab.graphics, 0, 41, tabWidth - 6, 5); tab.graphics.endFill();
                }
                browserText(tab, labels[t], 8, 10, tabWidth - 22, 27, 15, 0xFFFFFF, true, "center");
                tab.addEventListener(MouseEvent.CLICK, browserClick, false, 0, true);
                browserLayer.addChild(tab);
            }

            var toolbarY:Number = panelY + 126;
            var searchFrame:Sprite = new Sprite();
            searchFrame.x = panelX + 30; searchFrame.y = toolbarY;
            searchFrame.graphics.lineStyle(browserZone == "search" ? 2 : 1,
                browserZone == "search" ? 0xFFFFFF : 0x2E8BFF, 1);
            searchFrame.graphics.beginFill(0x07152B, 1); searchFrame.graphics.moveTo(0, 0);
            drawBrowserRect(searchFrame.graphics, 0, 0, 360, 42);
            searchFrame.graphics.endFill();
            browserLayer.addChild(searchFrame);
            browserSearch = new TextField();
            browserSearch.type = TextFieldType.INPUT; browserSearch.maxChars = 80;
            browserSearch.x = 13; browserSearch.y = 7; browserSearch.width = 334; browserSearch.height = 28;
            browserSearch.multiline = false; browserSearch.wordWrap = false; browserSearch.selectable = true;
            browserSearch.textColor = 0xFFFFFF; browserSearch.defaultTextFormat = new TextFormat("Arial", 16, 0xFFFFFF);
            browserSearch.text = browserSearchPending ? browserPendingQuery : String(browser.query);
            browserSearch.addEventListener(Event.CHANGE, browserSearchChanged, false, 0, true);
            browserSearch.addEventListener(FocusEvent.FOCUS_IN, browserSearchFocusIn, false, 0, true);
            browserSearch.addEventListener(FocusEvent.FOCUS_OUT, browserSearchFocusOut, false, 0, true);
            searchFrame.addChild(browserSearch);
            if (browserSearch.text.length == 0)
                browserSearchHint = browserText(searchFrame, "Search", 14, 8, 330, 25, 16, 0x5A6E8F);
            browserText(browserLayer, String(browser.total) + " items", panelX + panelWidth - 250, toolbarY + 8,
                220, 26, 14, 0x9FB4D4, false, "right");

            var toolY:Number = panelY + 176;
            if (tools != null && tools.length > 0)
            {
                browserToolFocus = Math.max(0, Math.min(browserToolFocus, tools.length - 1));
                var toolGap:Number = 5;
                var toolWidth:Number = (panelWidth - 60 - toolGap * (tools.length - 1)) / tools.length;
                for (var u:int = 0; u < tools.length; ++u)
                {
                    var tool:Object = tools[u];
                    var toolSprite:Sprite = new Sprite();
                    toolSprite.name = "browser.tool." + u;
                    toolSprite.x = panelX + 30 + u * (toolWidth + toolGap); toolSprite.y = toolY;
                    toolSprite.buttonMode = tool.enabled === true && !busy; toolSprite.mouseChildren = false;
                    toolSprite.graphics.lineStyle(browserZone == "tools" && browserToolFocus == u ? 2 : 1,
                        browserZone == "tools" && browserToolFocus == u ? 0xFFFFFF : 0x2E8BFF, 0.9);
                    toolSprite.graphics.moveTo(0, 0);
                    toolSprite.graphics.beginFill(tool.enabled === true && !busy ? 0x12305C : 0x16243B, 1);
                    drawBrowserRect(toolSprite.graphics, 0, 0, toolWidth, 36); toolSprite.graphics.endFill();
                    browserText(toolSprite, String(tool.label), 5, 8, toolWidth - 10, 22, 11,
                        tool.enabled === true && !busy ? 0xFFFFFF : 0x5A6E8F, true, "center");
                    toolSprite.addEventListener(MouseEvent.CLICK, browserClick, false, 0, true);
                    browserLayer.addChild(toolSprite);
                }
            }

            var bodyY:Number = panelY + 224;
            var bodyHeight:Number = panelHeight - 297;
            var listWidth:Number = Math.floor((panelWidth - 78) * 0.64);
            var detailX:Number = panelX + 42 + listWidth;
            var detailWidth:Number = panelX + panelWidth - 30 - detailX;
            var rowGap:Number = 5;
            var rowHeight:Number = Math.max(26, Math.floor((bodyHeight - rowGap * 7) / BROWSER_ROWS));
            var state:String = String(browser.state);

            if (state != "ready")
            {
                var stateText:String = state == "loading" ? "Loading this source…" :
                    state == "error" ? "Could not load this source." :
                    String(browser.query).length > 0 ? "No results for “" + String(browser.query) + "”" :
                    "No items are available.";
                g.lineStyle(1, 0x2E8BFF, 0.7); g.beginFill(0x07152B, 1);
                g.moveTo(panelX + 30, bodyY);
                drawBrowserRect(g, panelX + 30, bodyY, listWidth, bodyHeight); g.endFill();
                browserText(browserLayer, stateText, panelX + 60, bodyY + bodyHeight / 2 - 20,
                    listWidth - 60, 48, 18, state == "error" ? 0xFF5A5A : 0x9FB4D4, true, "center");
            }
            else if (rows != null)
            {
                var last:int = Math.min(rows.length, browserTop + BROWSER_ROWS);
                for (var r:int = browserTop; r < last; ++r)
                {
                    var row:Object = rows[r];
                    var rowSprite:Sprite = new Sprite();
                    rowSprite.name = "browser.row." + r;
                    rowSprite.x = panelX + 30; rowSprite.y = bodyY + (r - browserTop) * (rowHeight + rowGap);
                    rowSprite.buttonMode = true; rowSprite.mouseChildren = false;
                    var rowSelected:Boolean = selected != null && String(selected.key) == String(row.key);
                    rowSprite.graphics.lineStyle(rowSelected ? 3 : 1, rowSelected ? 0xFFFFFF : 0x173A69, 1);
                    rowSprite.graphics.moveTo(0, 0);
                    rowSprite.graphics.beginFill(rowSelected ? 0x1A4A8C : ((r & 1) == 0 ? 0x10264A : 0x0D2140), 1);
                    drawBrowserRect(rowSprite.graphics, 0, 0, listWidth - 12, rowHeight); rowSprite.graphics.endFill();
                    rowSprite.graphics.lineStyle(2, 0x2E8BFF, 0.9); rowSprite.graphics.beginFill(0x08162D, 1);
                    rowSprite.graphics.moveTo(10, 4);
                    drawBrowserRect(rowSprite.graphics, 10, 4, 78, rowHeight - 8); rowSprite.graphics.endFill();
                    if (!(String(browser.tab) == "lessons" && String(row.key) == "lesson:power-shots" && lessonPreviewState == 2))
                    {
                        rowSprite.graphics.moveTo(22, rowHeight - 8); rowSprite.graphics.lineTo(42, 8);
                        rowSprite.graphics.lineTo(57, rowHeight - 10); rowSprite.graphics.lineTo(76, 7);
                    }
                    if (String(browser.tab) == "lessons" && String(row.key) == "lesson:power-shots")
                    {
                        loadLessonPreview();
                        if (lessonPreviewState == 2)
                        {
                            var thumbnail:Bitmap = new Bitmap((lessonPreview.content as Bitmap).bitmapData);
                            thumbnail.smoothing = true;
                            thumbnail.scaleX = thumbnail.scaleY = Math.min(78 / 400, (rowHeight - 8) / 225);
                            thumbnail.x = 10 + (78 - thumbnail.width) / 2;
                            thumbnail.y = (rowHeight - thumbnail.height) / 2;
                            rowSprite.addChild(thumbnail);
                        }
                    }
                    var compactRow:Boolean = rowHeight < 48;
                    browserText(rowSprite, String(row.title), 102, compactRow ? Math.max(2, (rowHeight - 23) / 2) : 8,
                        listWidth - 190, compactRow ? 23 : 27, compactRow ? 13 : 16, 0xFFFFFF, true);
                    if (!compactRow)
                        browserText(rowSprite, String(row.subtitle), 102, rowHeight - 27,
                            listWidth - 190, 21, 12, 0x9FB4D4);
                    rowSprite.addEventListener(MouseEvent.CLICK, browserClick, false, 0, true);
                    rowSprite.addEventListener(MouseEvent.MOUSE_OVER, browserRowOver, false, 0, true);
                    browserLayer.addChild(rowSprite);
                }
                if (Number(browser.total) > BROWSER_ROWS)
                {
                    var trackX:Number = panelX + 30 + listWidth - 7;
                    g.beginFill(0x13284A, 1); g.moveTo(trackX, bodyY);
                    drawBrowserRect(g, trackX, bodyY, 6, bodyHeight); g.endFill();
                    var thumbHeight:Number = Math.max(34, bodyHeight * BROWSER_ROWS / Number(browser.total));
                    var maximum:Number = Math.max(1, Number(browser.total) - BROWSER_ROWS);
                    var scroll:Number = Math.min(maximum, Number(browser.offset) + browserTop);
                    var thumbY:Number = bodyY + (bodyHeight - thumbHeight) * scroll / maximum;
                    g.beginFill(0x2E8BFF, 1); g.moveTo(trackX, thumbY);
                    drawBrowserRect(g, trackX, thumbY, 6, thumbHeight); g.endFill();
                }
            }

            g.lineStyle(1, 0x2E8BFF, 0.8); g.beginFill(0x07152B, 0.96);
            g.moveTo(detailX, bodyY);
            drawBrowserRect(g, detailX, bodyY, detailWidth, bodyHeight); g.endFill();
            if (selected != null)
            {
                var previewHeight:Number = Math.max(64, Math.min(124, bodyHeight * 0.22));
                g.lineStyle(2, 0x2E8BFF, 0.8); g.beginFill(0x10264A, 1);
                g.moveTo(detailX + 18, bodyY + 18);
                drawBrowserRect(g, detailX + 18, bodyY + 18, detailWidth - 36, previewHeight); g.endFill();
                if (!(String(browser.tab) == "lessons" && String(selected.key) == "lesson:power-shots" && lessonPreviewState == 2))
                {
                    g.moveTo(detailX + 42, bodyY + previewHeight + 8); g.lineTo(detailX + 118, bodyY + 34);
                    g.lineTo(detailX + 188, bodyY + previewHeight - 2); g.lineTo(detailX + detailWidth - 42, bodyY + 30);
                }
                if (String(browser.tab) == "lessons" && String(selected.key) == "lesson:power-shots")
                {
                    loadLessonPreview();
                    if (lessonPreviewState == 2)
                    {
                        lessonPreview.scaleX = lessonPreview.scaleY = Math.min((detailWidth - 36) / 400, previewHeight / 225);
                        lessonPreview.x = detailX + (detailWidth - lessonPreview.width) / 2;
                        lessonPreview.y = bodyY + 18 + (previewHeight - lessonPreview.height) / 2;
                        lessonPreview.visible = true;
                    }
                }
                var titleY:Number = bodyY + previewHeight + 29;
                var subtitleY:Number = titleY + 48;
                var primaryY:Number = bodyY + bodyHeight - 78;
                var hasReason:Boolean = String(selected.reason).length > 0 && bodyHeight >= 330;
                var reasonY:Number = primaryY - (hasReason ? 50 : 8);
                var copyY:Number = subtitleY + 37;
                var copyHeight:Number = Math.max(0, reasonY - copyY - 5);
                browserText(browserLayer, String(selected.title), detailX + 20, titleY,
                    detailWidth - 40, 44, bodyHeight < 400 ? 18 : 22, 0xFFFFFF, true);
                browserText(browserLayer, String(selected.subtitle), detailX + 20, subtitleY,
                    detailWidth - 40, 32, 13, 0x9FB4D4);
                if (copyHeight >= 18)
                    browserText(browserLayer, String(selected.detail), detailX + 20, copyY,
                        detailWidth - 40, copyHeight, bodyHeight < 400 ? 13 : 15, 0xFFFFFF);
                if (hasReason)
                    browserText(browserLayer, String(selected.reason), detailX + 20, reasonY,
                        detailWidth - 40, 42, 12, 0x9FB4D4);

                var primary:Sprite = new Sprite();
                primary.name = "browser.primary";
                primary.x = detailX + detailWidth - 235; primary.y = primaryY;
                primary.buttonMode = selected.primary_enabled === true && !busy; primary.mouseChildren = false;
                primary.graphics.lineStyle(browserZone == "primary" ? 3 : 1,
                    browserZone == "primary" ? 0xFFFFFF : 0x2E8BFF, 1);
                primary.graphics.beginFill(selected.primary_enabled === true && !busy ? 0x2E8BFF : 0x263A59, 1);
                primary.graphics.moveTo(0, 0);
                drawBrowserRect(primary.graphics, 0, 0, 215, 55); primary.graphics.endFill();
                browserText(primary, String(selected.primary_label), 10, 15, 195, 27, 16,
                    selected.primary_enabled === true && !busy ? 0xFFFFFF : 0x5A6E8F, true, "center");
                primary.addEventListener(MouseEvent.CLICK, browserClick, false, 0, true);
                browserLayer.addChild(primary);
            }
            else
                browserText(browserLayer, "Choose an item to see its details.", detailX + 30,
                    bodyY + bodyHeight / 2 - 20, detailWidth - 60, 45, 16, 0x9FB4D4, false, "center");

            if (view.body != null && String(view.body).indexOf("Could not finish: ") == 0)
                browserText(browserLayer, String(view.body).split("\n\n")[0].substr(0, 360),
                    panelX + 30, panelY + panelHeight - 72, panelWidth - 60, 24, 12, 0xFFB26B);
            browserText(browserLayer, "LEFT / RIGHT TABS OR ACTION    UP / DOWN BROWSE    ENTER / CROSS START    ESC BACK",
                panelX + 30, panelY + panelHeight - 48, panelWidth - 60, 28, 12, 0x9FB4D4, false, "center");
            browserSearchEditing = searchWasEditing;
            if (searchWasEditing && stage != null && browserSearch != null)
            {
                stage.focus = browserSearch;
                browserSearch.setSelection(Math.min(searchBegin, browserSearch.text.length),
                    Math.min(searchEnd, browserSearch.text.length));
            }
        }

        private function browserClick(event:MouseEvent) : void
        {
            if (busy || event.currentTarget == null) return;
            var targetName:String = String(event.currentTarget.name);
            if (targetName.indexOf("browser.tab.") == 0)
            {
                var tab:String = targetName.substr(12);
                browserTabFocus = ["lessons", "workshop", "mods"].indexOf(tab);
                browserZone = "tabs";
                browserCommand("tab", tab);
            }
            else if (targetName.indexOf("browser.tool.") == 0)
            {
                browserToolFocus = int(targetName.substr(13));
                browserZone = "tools";
                activateBrowserTool();
            }
            else if (targetName.indexOf("browser.row.") == 0)
            {
                browserZone = "rows";
                selectBrowserIndex(int(targetName.substr(12)));
            }
            else if (targetName == "browser.primary") activateBrowserPrimary();
        }

        private function browserRowOver(event:MouseEvent) : void
        {
            if (busy || event.currentTarget == null) return;
            var index:int = int(String(event.currentTarget.name).substr(12));
            var rows:Array = view.browser.rows as Array;
            if (rows != null && index >= 0 && index < rows.length && browserZone == "rows" &&
                selectedRowKey == String(rows[index].key)) return;
            browserZone = "rows";
            selectBrowserIndex(index);
        }

        private function browserSearchFocusIn(event:FocusEvent) : void
        {
            browserZone = "search";
            browserSearchEditing = true;
            if (browserSearchHint != null) browserSearchHint.visible = false;
        }

        private function browserSearchFocusOut(event:FocusEvent) : void
        {
            browserSearchEditing = false;
            if (browserSearchHint != null && browserSearch != null)
                browserSearchHint.visible = browserSearch.text.length == 0;
        }

        private function browserSearchChanged(event:Event) : void
        {
            if (browserSearch == null || view == null || view.browser == null) return;
            var raw:String = browserSearch.text;
            var clean:String = "";
            for (var i:int = 0; i < raw.length && clean.length < 80; ++i)
            {
                var code:int = raw.charCodeAt(i);
                if (code >= 32 && code <= 126 && code != 60 && code != 62 && code != 38)
                    clean += raw.charAt(i);
            }
            if (clean != raw) browserSearch.text = clean;
            if (browserSearchHint != null) browserSearchHint.visible = clean.length == 0 && !browserSearchEditing;
            browserPendingQuery = clean;
            browserSearchPending = true;
            browserSearchRetries = 0;
            if (!busy && browserPendingQuery != String(view.browser.query))
                browserCommand("search", browserPendingQuery);
        }

        private function normalizeBrowserSelection() : void
        {
            if (view == null || view.browser == null) return;
            var rows:Array = view.browser.rows as Array;
            if (rows == null || rows.length == 0)
            {
                selectedRowKey = ""; browserTop = 0; return;
            }
            var index:int = browserRowIndex();
            if (index < 0)
            {
                index = 0;
                selectedRowKey = String(rows[0].key);
            }
            var maximum:int = Math.max(0, rows.length - BROWSER_ROWS);
            browserTop = Math.max(0, Math.min(browserTop, maximum));
            if (index < browserTop) browserTop = index;
            else if (index >= browserTop + BROWSER_ROWS) browserTop = Math.min(maximum, index - BROWSER_ROWS + 1);
        }

        private function selectedBrowserRow() : Object
        {
            if (view == null || view.browser == null) return null;
            var rows:Array = view.browser.rows as Array;
            var index:int = browserRowIndex();
            return rows != null && index >= 0 && index < rows.length ? rows[index] : null;
        }

        private function browserRowIndex() : int
        {
            if (view == null || view.browser == null) return -1;
            var rows:Array = view.browser.rows as Array;
            if (rows == null) return -1;
            for (var i:int = 0; i < rows.length; ++i)
                if (String(rows[i].key) == selectedRowKey) return i;
            return -1;
        }

        private function selectBrowserIndex(index:int) : void
        {
            var rows:Array = view.browser.rows as Array;
            if (rows == null || index < 0 || index >= rows.length) return;
            selectedRowKey = String(rows[index].key);
            normalizeBrowserSelection();
            renderBrowser();
        }

        private function moveBrowserRow(direction:int) : void
        {
            var rows:Array = view.browser.rows as Array;
            if (rows == null || rows.length == 0)
            {
                if (direction > 0 && view.browser.has_more == true)
                    browserCommand("scroll", "down");
                return;
            }
            var index:int = browserRowIndex();
            if (index < 0) index = 0;
            var next:int = index + direction;
            if (next >= 0 && next < rows.length)
            {
                selectBrowserIndex(next);
                return;
            }
            var offset:Number = Number(view.browser.offset);
            var total:Number = Number(view.browser.total);
            if ((direction < 0 && offset > 0) || (direction > 0 && offset + rows.length < total))
            {
                browserPendingMove = direction;
                browserCommand("scroll", direction < 0 ? "up" : "down");
            }
            else if (direction < 0)
            {
                browserZone = "tabs";
                renderBrowser();
            }
            else if (view.browser.has_more == true)
            {
                // Last displayed row of a catalog that still has a next page.
                // One explicit user scroll requests the bounded append.
                browserCommand("scroll", "down");
            }
        }

        private function applyPendingBrowserMove() : void
        {
            if (browserPendingMove == 0 || view == null || view.browser == null) return;
            var direction:int = browserPendingMove;
            browserPendingMove = 0;
            var index:int = browserRowIndex();
            var rows:Array = view.browser.rows as Array;
            if (rows != null && index + direction >= 0 && index + direction < rows.length)
                selectedRowKey = String(rows[index + direction].key);
            normalizeBrowserSelection();
        }

        private function browserLeft() : void
        {
            if (browserZone == "tabs") browserTabFocus = (browserTabFocus + 2) % 3;
            else if (browserZone == "tools")
            {
                var tools:Array = view.browser.tools as Array;
                if (tools != null && tools.length > 0)
                    browserToolFocus = (browserToolFocus + tools.length - 1) % tools.length;
            }
            else if (browserZone == "primary") browserZone = "rows";
            renderBrowser();
        }

        private function browserRight() : void
        {
            if (browserZone == "tabs") browserTabFocus = (browserTabFocus + 1) % 3;
            else if (browserZone == "tools")
            {
                var tools:Array = view.browser.tools as Array;
                if (tools != null && tools.length > 0) browserToolFocus = (browserToolFocus + 1) % tools.length;
            }
            else if (browserZone == "rows") browserZone = "primary";
            renderBrowser();
        }

        private function browserUp() : void
        {
            if (browserZone == "rows" && browserRowIndex() == 0 && Number(view.browser.offset) == 0)
            {
                var tools:Array = view.browser.tools as Array;
                browserZone = tools != null && tools.length > 0 ? "tools" : "tabs";
                renderBrowser();
            }
            else if (browserZone == "rows") moveBrowserRow(-1);
            else if (browserZone == "tools") { browserZone = "tabs"; renderBrowser(); }
            else if (browserZone == "primary") { browserZone = "rows"; renderBrowser(); }
            else if (browserZone == "search") { browserZone = "tabs"; renderBrowser(); }
        }

        private function browserDown() : void
        {
            if (browserZone == "tabs")
            {
                var tools:Array = view.browser.tools as Array;
                browserZone = tools != null && tools.length > 0 ? "tools" : "rows";
                renderBrowser();
            }
            else if (browserZone == "search" || browserZone == "tools") { browserZone = "rows"; renderBrowser(); }
            else if (browserZone == "rows") moveBrowserRow(1);
        }

        private function cycleBrowserFocus(direction:int) : void
        {
            var zones:Array = ["tabs", "search"];
            var tools:Array = view.browser.tools as Array;
            if (tools != null && tools.length > 0) zones.push("tools");
            zones.push("rows", "primary");
            var index:int = zones.indexOf(browserZone);
            if (index < 0) index = 0;
            browserZone = String(zones[(index + direction + zones.length) % zones.length]);
            if (browserZone == "search" && browserSearch != null && stage != null)
            {
                browserSearchEditing = true;
                stage.focus = browserSearch;
                browserSearch.setSelection(browserSearch.text.length, browserSearch.text.length);
            }
            else renderBrowser();
        }

        private function activateBrowserFocus() : void
        {
            if (browserZone == "tabs")
                browserCommand("tab", ["lessons", "workshop", "mods"][browserTabFocus]);
            else if (browserZone == "tools") activateBrowserTool();
            else if (browserZone == "search" && browserSearch != null && stage != null)
            {
                browserSearchEditing = true; stage.focus = browserSearch;
            }
            else activateBrowserPrimary();
        }

        private function activateBrowserTool() : void
        {
            var tools:Array = view.browser.tools as Array;
            if (tools == null || browserToolFocus < 0 || browserToolFocus >= tools.length) return;
            var tool:Object = tools[browserToolFocus];
            if (tool.enabled === true) browserCommand("tool", String(tool.key));
        }

        private function activateBrowserPrimary() : void
        {
            var selected:Object = selectedBrowserRow();
            if (selected != null && selected.primary_enabled === true)
            {
                browserZone = "primary";
                browserCommand("primary", String(selected.key));
            }
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
            queueRefresh();
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
            queueRefresh();
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
                if (incoming.browser != null)
                {
                    var browser:Object = incoming.browser;
                    if (!(browser.rows is Array) || browser.rows.length > 32 || !(browser.query is String) ||
                        browser.query.length > 80 || !(browser.revision is String) || !(browser.tools is Array) ||
                        browser.tools.length > 8 || browser.active !== true ||
                        !isFinite(Number(browser.offset)) || Number(browser.offset) < 0 ||
                        Math.floor(Number(browser.offset)) != Number(browser.offset) ||
                        !isFinite(Number(browser.total)) || Number(browser.total) < 0 ||
                        Math.floor(Number(browser.total)) != Number(browser.total) ||
                        Number(browser.offset) + browser.rows.length > Number(browser.total) ||
                        ["lessons", "workshop", "mods"].indexOf(browser.tab) < 0 ||
                        ["ready", "empty", "loading", "error"].indexOf(browser.state) < 0)
                        throw new Error("Invalid browser");
                    for each (var row:Object in browser.rows)
                        if (!(row.key is String) || row.key.length > 128 || !(row.title is String) ||
                            row.title.length > 240 || !(row.subtitle is String) || row.subtitle.length > 240 ||
                            !(row.detail is String) || row.detail.length > 240 || !(row.primary_label is String) ||
                            row.primary_label.length > 80 || !(row.reason is String) || row.reason.length > 240 ||
                            !(row.primary_enabled is Boolean) || !(row.favorite is Boolean))
                            throw new Error("Invalid browser row");
                    for each (var tool:Object in browser.tools)
                        if (!(tool.key is String) || tool.key.length > 128 || !(tool.label is String) ||
                            tool.label.length > 80 || !(tool.reason is String) || tool.reason.length > 240 ||
                            !(tool.enabled is Boolean))
                            throw new Error("Invalid browser tool");
                }
                if (!validView(incoming)) { loseConnection(); return; }
                if (getTimer() - lastHello >= 1000 ||
                    (isFrontMenu() && String(incoming.generation) != generation))
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
                    if (view.browser != null) applyPendingBrowserMove();
                    else
                    {
                        browserPendingMove = 0;
                        browserSearchPending = false;
                        browserPendingQuery = "";
                    }
                    refreshMenu();
                    if (view.browser != null && browserSearchPending)
                    {
                        if (browserPendingQuery == String(view.browser.query)) browserSearchPending = false;
                        else browserCommand("search", browserPendingQuery);
                    }
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
                        // A coalesced edit may have arrived while its predecessor
                        // was waiting for the new generation's READY handshake.
                        if (view.browser != null && browserSearchPending &&
                            browserPendingQuery != String(view.browser.query))
                        {
                            if (browserSearchRetries < 1)
                            {
                                ++browserSearchRetries;
                                browserCommand("search", browserPendingQuery);
                            }
                            else
                            {
                                browserSearchPending = false;
                                browserPendingQuery = String(view.browser.query);
                                refreshMenu();
                            }
                        }
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

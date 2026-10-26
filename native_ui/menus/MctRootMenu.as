package menus
{
    import flash.events.Event;
    import com.adobe.serialization.json.JSON;
    import flash.display.Graphics;
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
            var tabs:Array = ["lessons", "workshop", "mods", "favorites"];
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
                else if (event.keyCode == 27 && String(view.browser.query).length > 0 && !busy)
                {
                    event.preventDefault();
                    event.stopImmediatePropagation();
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
            while (browserLayer.numChildren > 0) browserLayer.removeChildAt(0);
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
            while (browserLayer.numChildren > 0) browserLayer.removeChildAt(0);
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

            var tabs:Array = ["lessons", "workshop", "mods", "favorites"];
            var labels:Array = ["LESSONS", "WORKSHOP", "MODS", "FAVORITES"];
            var tabY:Number = panelY + 68;
            var tabWidth:Number = Math.min(210, (panelWidth - 60) / 4);
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
                    String(browser.tab) == "favorites" ? "No favorites yet." : "No items are available.";
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
                    rowSprite.graphics.moveTo(22, rowHeight - 8); rowSprite.graphics.lineTo(42, 8);
                    rowSprite.graphics.lineTo(57, rowHeight - 10); rowSprite.graphics.lineTo(76, 7);
                    var compactRow:Boolean = rowHeight < 48;
                    browserText(rowSprite, String(row.title), 102, compactRow ? Math.max(2, (rowHeight - 23) / 2) : 8,
                        listWidth - 190, compactRow ? 23 : 27, compactRow ? 13 : 16, 0xFFFFFF, true);
                    if (!compactRow)
                        browserText(rowSprite, String(row.subtitle), 102, rowHeight - 27,
                            listWidth - 190, 21, 12, 0x9FB4D4);
                    if (row.favorite === true)
                        drawStar(rowSprite.graphics, listWidth - 55, rowHeight / 2, 10, 4, true, 0xFF8A1F);
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
                g.moveTo(detailX + 42, bodyY + previewHeight + 8); g.lineTo(detailX + 118, bodyY + 34);
                g.lineTo(detailX + 188, bodyY + previewHeight - 2); g.lineTo(detailX + detailWidth - 42, bodyY + 30);
                var titleY:Number = bodyY + previewHeight + 29;
                var subtitleY:Number = titleY + 48;
                var primaryY:Number = bodyY + bodyHeight - 78;
                var hasReason:Boolean = String(selected.reason).length > 0 && bodyHeight >= 330;
                var reasonY:Number = primaryY - (hasReason ? 50 : 8);
                var copyY:Number = subtitleY + 37;
                var copyHeight:Number = Math.max(0, reasonY - copyY - 5);
                browserText(browserLayer, String(selected.title), detailX + 20, titleY,
                    detailWidth - 90, 44, bodyHeight < 400 ? 18 : 22, 0xFFFFFF, true);
                browserText(browserLayer, String(selected.subtitle), detailX + 20, subtitleY,
                    detailWidth - 40, 32, 13, 0x9FB4D4);
                if (copyHeight >= 18)
                    browserText(browserLayer, String(selected.detail), detailX + 20, copyY,
                        detailWidth - 40, copyHeight, bodyHeight < 400 ? 13 : 15, 0xFFFFFF);
                if (hasReason)
                    browserText(browserLayer, String(selected.reason), detailX + 20, reasonY,
                        detailWidth - 40, 42, 12, 0x9FB4D4);

                var favorite:Sprite = new Sprite();
                favorite.name = "browser.favorite"; favorite.x = detailX + detailWidth - 65; favorite.y = titleY + 3;
                favorite.buttonMode = true; favorite.mouseChildren = false;
                favorite.graphics.lineStyle(browserZone == "favorite" ? 2 : 1,
                    browserZone == "favorite" ? 0xFFFFFF : 0xFF8A1F, 1);
                favorite.graphics.beginFill(0x10264A, 1); favorite.graphics.moveTo(0, 0);
                drawBrowserRect(favorite.graphics, 0, 0, 42, 42);
                favorite.graphics.endFill();
                drawStar(favorite.graphics, 21, 21, 14, 6, selected.favorite === true, 0xFF8A1F);
                favorite.addEventListener(MouseEvent.CLICK, browserClick, false, 0, true);
                browserLayer.addChild(favorite);

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
                browserTabFocus = ["lessons", "workshop", "mods", "favorites"].indexOf(tab);
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
            else if (targetName == "browser.favorite") activateBrowserFavorite();
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
            if (browserZone == "tabs") browserTabFocus = (browserTabFocus + 3) % 4;
            else if (browserZone == "tools")
            {
                var tools:Array = view.browser.tools as Array;
                if (tools != null && tools.length > 0)
                    browserToolFocus = (browserToolFocus + tools.length - 1) % tools.length;
            }
            else if (browserZone == "primary" || browserZone == "favorite") browserZone = "rows";
            renderBrowser();
        }

        private function browserRight() : void
        {
            if (browserZone == "tabs") browserTabFocus = (browserTabFocus + 1) % 4;
            else if (browserZone == "tools")
            {
                var tools:Array = view.browser.tools as Array;
                if (tools != null && tools.length > 0) browserToolFocus = (browserToolFocus + 1) % tools.length;
            }
            else if (browserZone == "rows") browserZone = "primary";
            else if (browserZone == "favorite") browserZone = "primary";
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
            else if (browserZone == "primary") { browserZone = "favorite"; renderBrowser(); }
            else if (browserZone == "favorite") { browserZone = "rows"; renderBrowser(); }
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
            else if (browserZone == "favorite") { browserZone = "primary"; renderBrowser(); }
        }

        private function cycleBrowserFocus(direction:int) : void
        {
            var zones:Array = ["tabs", "search"];
            var tools:Array = view.browser.tools as Array;
            if (tools != null && tools.length > 0) zones.push("tools");
            zones.push("rows", "favorite", "primary");
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
                browserCommand("tab", ["lessons", "workshop", "mods", "favorites"][browserTabFocus]);
            else if (browserZone == "tools") activateBrowserTool();
            else if (browserZone == "favorite") activateBrowserFavorite();
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

        private function activateBrowserFavorite() : void
        {
            var selected:Object = selectedBrowserRow();
            if (selected != null)
            {
                browserZone = "favorite";
                browserCommand("favorite", String(selected.key));
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
                        ["lessons", "workshop", "mods", "favorites"].indexOf(browser.tab) < 0 ||
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
                if (getTimer() - lastHello >= 1000 || String(incoming.generation) != generation)
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
                            browserCommand("search", browserPendingQuery);
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

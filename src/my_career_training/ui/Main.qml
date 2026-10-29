import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1340; height: 900
    minimumWidth: 1000; minimumHeight: 720
    visible: true
    onClosing: function(close) { close.accepted = backend.request_close(); }
    title: "My Career Training"
    color: "#0c141d"
    font.family: "Segoe UI"
    font.pixelSize: 14 * root.textScale
    palette.window: "#0c141d"; palette.base: "#101b26"; palette.text: "#e8f0f5"
    palette.windowText: "#e8f0f5"; palette.placeholderText: "#8ba1b3"; palette.button: "#203241"; palette.buttonText: "#e8f0f5"
    palette.highlight: "#87c9ed"; palette.highlightedText: "#08131d"
    property var view: typeof backend !== "undefined" && backend ? backend.state || ({}) : ({})
    property var career: view.career || null
    property var settings: view.settings || ({})
    property var session: view.session || ({})
    property var season: career && career.seasons ? career.seasons[career.current_season || 0] || ({}) : ({})
    property string page: view.page || "home"
    property real textScale: Number(settings.text_scale || 1)
    property var selectedLesson: view.selected_lesson || null
    property var draftLineup: []
    property string recruitEditing: ""
    property var startingRecruits: ["anchor", "shield", "relay", "comet"]
    property string garageRecruit: "anchor"
    property bool onlineAwaiting: false
    property bool reviewOpen: false
    property string dismissedError: ""
    property var recruitPool: ["anchor", "shield", "relay", "comet", "orbit"]
    property bool locked: Boolean(career && career.pending_session) || Boolean(session.busy)
    function act(name, payload) { backend.dispatch(name, payload || {}); }
    function go(destination) { act("navigate", {page: destination}); }
    function club(id) {
        var clubs = season.clubs || [];
        if (!Array.isArray(clubs)) return clubs[id] ? clubs[id].name || id : id;
        for (var i=0;i<clubs.length;i++) if(clubs[i].id === id) return clubs[i].name;
        return id === "human" && career ? career.team_name : id || "Unknown club";
    }
    function recruit(id) { return career && career.recruits ? career.recruits[id] || ({name:id,role:id,level:1}) : ({name:id,role:id,level:1}); }
    function score(f) { var r = f.result; return r ? (r.home_score === undefined ? r.home : r.home_score) + " – " + (r.away_score === undefined ? r.away : r.away_score) : "vs"; }
    function lessonPref(key, fallback) {
        var id = selectedLesson ? selectedLesson.id : "";
        var prefs = (view.lesson_preferences || {})[id] || ({});
        if (prefs[key] !== undefined) return prefs[key];
        var defaults = selectedLesson ? selectedLesson.assistance_defaults || ({}) : ({});
        return defaults[key] !== undefined ? defaults[key] : fallback;
    }
    function variant(key, fallback) { var v = selectedLesson ? selectedLesson.variant || ({}) : ({}); return v[key] === undefined || v[key] === null ? fallback : v[key]; }
    function online() { onlineAwaiting = true; act("online_request"); onlineDialog.open(); }
    function toggleLineup(id) {
        var ids = draftLineup.slice(); var i = ids.indexOf(id);
        if (i >= 0) ids.splice(i,1); else if (ids.length < Number(career.format)-1) ids.push(id);
        draftLineup = ids;
    }
    function toggleStartingRecruit(id) {
        var ids=startingRecruits.slice(); var index=ids.indexOf(id);
        if(index>=0) ids.splice(index,1); else if(ids.length<4) ids.push(id);
        startingRecruits=ids;
    }
    function refreshDraft() { draftLineup = career && career.lineup ? career.lineup.slice() : []; }
    onPageChanged: { refreshDraft(); Qt.callLater(function(){if(pageScroll.contentItem) pageScroll.contentItem.contentY=0;}); }
    onCareerChanged: { refreshDraft(); }
    onViewChanged: {
        if (view.error && view.error !== dismissedError) errorDialog.open();
    }
    Component.onCompleted: { refreshDraft(); }
    Shortcut { sequence: "Alt+Left"; onActivated: root.go(root.career ? "hub" : "home") }
    Shortcut { sequence: "Escape"; onActivated: {
        if (onlineDialog.visible) onlineDialog.reject();
        else if (newCareerDialog.visible) newCareerDialog.reject();
        else if (recoveryDialog.visible) recoveryDialog.reject();
        else if (renameDialog.visible) renameDialog.reject();
        else if (errorDialog.visible) errorDialog.reject();
        else root.go(root.career ? "hub" : "home");
    } }
    RowLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            Layout.preferredWidth: 222; Layout.fillHeight: true
            color: "#101b25"; border.color: "#263442"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 20; spacing: 8
                RowLayout {
                    Layout.topMargin: 12; Layout.bottomMargin: 26; spacing: 11
                    Image { source: "icon.svg"; sourceSize.width: 34; sourceSize.height: 34; Layout.preferredWidth: 34; Layout.preferredHeight: 34 }
                    Copy { text: "MY CAREER\nTRAINING"; font.pixelSize: 14; font.weight: Font.DemiBold; font.letterSpacing: 1.6 }
                }
                Repeater {
                    model: [{id:"home",label:"Home",mark:"01"},{id:"hub",label:"Career hub",mark:"02"},{id:"squad",label:"Squad",mark:"03"},{id:"season",label:"Season",mark:"04"},{id:"training",label:"Training",mark:"05"},{id:"garage",label:"Garage",mark:"06"},{id:"community",label:"Community",mark:"07"}]
                    delegate: ActionButton { textScale:root.textScale;
                        required property var modelData
                        Layout.fillWidth: true; implicitHeight: 47
                        text: modelData.label; quiet: true
                        enabled: root.career !== null || ["home","training","community"].indexOf(modelData.id) >= 0
                        primary: root.page === modelData.id
                        onClicked: root.go(modelData.id)
                    }
                }
                Item { Layout.fillHeight: true }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#293a49"; Layout.bottomMargin: 12 }
                Copy { text: "YOUR GAME. YOUR SEASON."; tone: "small"; color: "#90a4b4"; Layout.fillWidth: true; font.letterSpacing: 1 }
                ActionButton { textScale:root.textScale; text: "Play Online  ↗"; Layout.fillWidth: true; quiet: true; onClicked: root.online() }
                ActionButton { textScale:root.textScale; text: "Settings"; Layout.fillWidth: true; quiet: true; primary: root.page === "settings"; onClicked: root.go("settings") }
                Copy { text: "0.1.0 · Testing preview"; tone:"small"; color:"#71889a"; Layout.topMargin: 12 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 80; color: "#0f1923"
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 32; anchors.rightMargin: 32
                    Copy { text: root.career ? root.career.team_name : "A new chapter starts here"; tone: "heading"; scale: root.textScale; Layout.fillWidth: true }
                    Rectangle { width: 7; height: 7; radius: 4; color: root.session.busy ? "#efa466" : "#87c9ed" }
                    Copy { text: root.session.state || "Ready"; tone:"small"; color:"#a3b8c8"; scale: root.textScale }
                }
            }
            Rectangle {
                visible: Boolean(root.session.message || root.view.notice)
                Layout.fillWidth: true; implicitHeight: statusText.implicitHeight + 28
                color: root.session.busy ? "#183348" : "#172c36"
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 32; anchors.rightMargin: 24
                    Copy { id: statusText; Layout.fillWidth: true; text: root.session.message || root.view.notice || ""; scale: root.textScale }
                    ActionButton { textScale:root.textScale; text:"Retry online transition"; visible:root.session.can_retry || false; enabled:!root.session.busy; onClicked:root.act("online_retry") }
                    BusyIndicator { running: root.session.busy || false; visible: running; Layout.preferredHeight: 30; Layout.preferredWidth: 30 }
                }
            }
            ScrollView {
                id: pageScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    width: pageScroll.availableWidth; spacing: 22
                    Item { Layout.preferredHeight: 8 }
                    Loader {
                        Layout.fillWidth: true; Layout.leftMargin: 32; Layout.rightMargin: 32
                        sourceComponent: root.page === "hub" ? hubPage : root.page === "squad" ? squadPage : root.page === "season" ? seasonPage : root.page === "training" ? trainingPage : root.page === "garage" ? garagePage : root.page === "community" ? communityPage : root.page === "settings" ? settingsPage : homePage
                    }
                    Copy { text: "Local career companion · Rocket League runs in its own window"; tone:"small"; color:"#6f8799"; Layout.leftMargin: 32; Layout.bottomMargin: 24; Layout.topMargin: 4 }
                }
            }
        }
    }
    Component {
        id: homePage
        ColumnLayout {
            spacing: 22
            Panel {
                Layout.fillWidth: true; implicitHeight: Math.max(310, 310 * root.textScale); color: "#172938"; clip: true
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.maximumWidth: 560; spacing: 18
                        Copy { text: "BUILD A TEAM. FIND YOUR EDGE."; tone:"small"; color:"#a5cce0"; font.letterSpacing: 2; scale: root.textScale }
                        Copy { text: "Make the next\nseason yours."; tone:"hero"; scale: root.textScale; Layout.fillWidth: true }
                        Copy { text: "Captain your squad in the real game. Build chemistry across a short season, or take time to practice your next move."; tone:"muted"; scale: root.textScale; Layout.fillWidth: true }
                        RowLayout {
                            ActionButton { textScale:root.textScale; text: root.career ? "Continue career  →" : "Create your club  →"; primary: true; onClicked: root.career ? root.go("hub") : newCareerDialog.open() }
                            ActionButton { textScale:root.textScale; text: "Explore training"; quiet:true; onClicked: root.go("training") }
                        }
                    }
                    OrbitArt { Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 200; Layout.maximumWidth: 350 }
                }
            }
            RowLayout {
                spacing: 18; Layout.fillWidth: true
                Panel {
                    Layout.fillWidth: true; Layout.alignment: Qt.AlignTop
                    Copy { text: "One captain. Five personalities."; tone:"heading"; scale: root.textScale; Layout.fillWidth: true }
                    Copy { text: "You drive. Four specialist recruits make up your squad, with a starting lineup for every format from 1v1 to 4v4."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
                    ActionButton { textScale:root.textScale; text: root.career ? "Meet your squad" : "New career"; onClicked: root.career ? root.go("squad") : newCareerDialog.open() }
                }
                Panel {
                    Layout.fillWidth: true; Layout.alignment: Qt.AlignTop
                    Copy { text: "Practice on your terms."; tone:"heading"; scale:root.textScale; Layout.fillWidth:true }
                    Copy { text: "Eight optional lessons. Switch each help setting independently, retry at any time, and learn from your own recorded attempts."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
                    ActionButton { textScale:root.textScale; text: "Choose a lesson"; onClicked: root.go("training") }
                }
            }
            Panel {
                Layout.fillWidth: true
                Copy { text: "Before your first kickoff"; tone:"heading"; scale: root.textScale }
                Copy { visible:root.view.setup_required || false; text:"First-time setup is waiting. Select your launcher in Settings, then choose Use selected launcher."; Layout.fillWidth:true; color:"#91d4f5"; scale:root.textScale }
                Copy { text: "Select Steam or Epic and check your game location in Settings. Career matches use the supported offline bot environment. Play Online saves your progress and opens the normal game entry."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
                RowLayout {
                    ActionButton { textScale:root.textScale; text: "Open setup & diagnostics"; onClicked: root.go("settings") }
                    ActionButton { textScale:root.textScale; text:"Try calibration match"; enabled:!root.locked && !root.session.results_pending_choice; onClicked:root.act("calibration") }
                }
                Copy { text:"Calibration is an optional exhibition. It does not record a league result."; tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
            }
        }
    }
    Component {
        id: hubPage
        ColumnLayout {
            spacing: 22
            Copy { text: "Career hub"; tone:"title"; scale:root.textScale }
            Copy { text: root.career ? "Season " + (Number(root.career.current_season || 0)+1) + "  /  " + root.career.format + "v" + root.career.format + " Soccar" : "Create a career to take the field."; tone:"muted"; scale:root.textScale }
            Panel {
                visible: Boolean(root.career && root.career.pending_session); Layout.fillWidth: true; color:"#30271f"; border.color:"#76553b"
                Copy { text:"Unfinished session"; tone:"heading"; scale:root.textScale }
                Copy { text:"Your last session has not recorded a completed result. Completed progress is safe. Finish recovery before changing your lineup or restarting from kickoff."; Layout.fillWidth:true; scale:root.textScale }
                RowLayout {
                    ActionButton { textScale:root.textScale; text:"Abandon unfinished attempt"; danger:true; enabled: !root.session.busy; onClicked: abandonDialog.open() }
                    ActionButton { textScale:root.textScale; text:"Repair a missing result…"; enabled:!root.session.busy && root.session.state!=="Playing" && root.session.state!=="playing"; onClicked:recoveryDialog.open() }
                }
            }
            Panel {
                Layout.fillWidth:true; visible: root.career !== null
                Copy { text: root.view.next_fixture ? "NEXT FIXTURE  ·  ROUND " + root.view.next_fixture.round : "SEASON COMPLETE"; tone:"small"; color:"#91d4f5"; scale:root.textScale; font.letterSpacing:1.6 }
                Copy { text: root.view.next_fixture ? root.club(root.view.next_fixture.home) + "  vs  " + root.club(root.view.next_fixture.away) : root.season.champion ? root.club(root.season.champion) + " are champions" : "Your season is ready to review"; tone:"title"; scale:root.textScale; Layout.fillWidth:true }
                Copy { text: root.view.next_fixture ? (root.view.next_fixture.map || "Standard arena") + "  ·  Five minutes + overtime  ·  " + root.view.next_fixture.format + "v" + root.view.next_fixture.format : "Keep your squad, levels, lessons, and rewards into the next season."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
                RowLayout {
                    ActionButton { textScale:root.textScale; text: root.view.next_fixture ? "Play match  →" : "Start next season"; primary:true; enabled: !root.locked; onClicked: root.act(root.view.next_fixture ? "play_match" : "next_season") }
                    ActionButton { textScale:root.textScale; text:"View season"; onClicked: root.go("season") }
                    ActionButton { textScale:root.textScale; text:"Play Online  ↗"; quiet:true; onClicked: root.online() }
                }
            }
            RowLayout {
                spacing:18; Layout.fillWidth:true
                Panel {
                    Layout.fillWidth:true; Layout.alignment:Qt.AlignTop
                    Copy { text:"Starting squad"; tone:"heading"; scale:root.textScale }
                    Copy { text:"You · Human captain"; scale:root.textScale }
                    Repeater { model: root.career ? root.career.lineup || [] : []; delegate: Copy { required property var modelData; text: root.recruit(modelData).name + " · " + root.recruit(modelData).role + " · Lv " + root.recruit(modelData).level; scale:root.textScale } }
                    Copy { visible: root.career !== null && Number(root.career.format)===1; text:"Solo fixture · all recruits on the bench"; tone:"muted"; scale:root.textScale }
                    ActionButton { textScale:root.textScale; text:"Manage lineup"; onClicked:root.go("squad") }
                }
                Panel {
                    Layout.fillWidth:true; Layout.alignment:Qt.AlignTop
                    Copy { text:"League leaders"; tone:"heading"; scale:root.textScale }
                    Repeater { model: (root.view.standings || []).slice(0,4); delegate: RowLayout { required property var modelData; required property int index; Layout.fillWidth:true; Copy { text:(index+1)+"."; color:"#91d4f5"; Layout.preferredWidth:26 } Copy { text:modelData.name || root.club(modelData.club_id || modelData.id); Layout.fillWidth:true; scale:root.textScale } Copy { text: String(modelData.points || 0) + " pts"; scale:root.textScale } } }
                    ActionButton { textScale:root.textScale; text:"Full table"; quiet:true; onClicked:root.go("season") }
                }
            }
            Panel {
                visible: Boolean(root.view.latest_result); Layout.fillWidth:true
                Copy { text:"Latest match"; tone:"heading"; scale:root.textScale }
                Copy { text: {
                    var result=root.view.latest_result;
                    if(!result) return "";
                    var r=result.result || result;
                    var home=r.home_score === undefined ? r.home : r.home_score;
                    var away=r.away_score === undefined ? r.away : r.away_score;
                    return home !== undefined && away !== undefined ? (result.home ? root.club(result.home)+"  " : "")+home+" – "+away+(result.away ? "  "+root.club(result.away) : "") : r.summary || r.message || "Completed match saved";
                } tone:"title"; Layout.fillWidth:true; scale:root.textScale }
                ActionButton { textScale:root.textScale; text:"Continue"; primary:true; onClicked:root.go("season") }
                ActionButton {
                    textScale:root.textScale; quiet:true
                    text:root.reviewOpen ? "Hide optional match review" : "Review this match"
                    visible:Boolean(root.view.latest_result && (root.view.latest_result.review || []).length)
                    onClicked:root.reviewOpen = !root.reviewOpen
                }
                Copy { visible:root.reviewOpen; text:"Observed moments and optional coaching suggestions. These never affect your progress."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                Repeater {
                    model:root.reviewOpen && root.view.latest_result ? root.view.latest_result.review || [] : []
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth:true; spacing:6
                        Copy { text:Number(modelData.time).toFixed(1)+"s · "+modelData.title; tone:"heading"; Layout.fillWidth:true; scale:root.textScale }
                        Copy { text:modelData.evidence; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                        Copy { text:modelData.suggestion; visible:Boolean(modelData.suggestion); Layout.fillWidth:true; scale:root.textScale }
                    }
                }
            }
        }
    }
    Component {
        id: squadPage
        ColumnLayout {
            spacing:20
            Copy { text:"Your squad"; tone:"title"; scale:root.textScale }
            Copy { text:"One human captain + four recruits. Select " + (root.career ? Number(root.career.format)-1 : 0) + " teammate(s) for your next fixture. Changes apply between matches."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            Panel {
                Layout.fillWidth:true
                RowLayout {
                    Copy { text:"YOU"; tone:"small"; color:"#f8b477"; Layout.preferredWidth:70 }
                    Copy { text:"Human captain"; tone:"heading"; Layout.fillWidth:true; scale:root.textScale }
                    Copy { text:"Always starting · Normal controls"; tone:"muted"; scale:root.textScale }
                }
            }
            Repeater {
                model: root.career ? root.career.squad || [] : []
                delegate: Panel {
                    required property var modelData
                    Layout.fillWidth:true
                    RowLayout {
                        Layout.fillWidth:true; spacing:18
                        Rectangle { width:52; height:52; radius:12; color:root.draftLineup.indexOf(modelData)>=0 ? "#2f536b" : "#23303c"; Copy { anchors.centerIn:parent; text:root.recruit(modelData).name.charAt(0); tone:"heading"; color:"#a9d8ef" } }
                        ColumnLayout { Layout.fillWidth:true; Copy { text:root.recruit(modelData).name; tone:"heading"; scale:root.textScale } Copy { text:root.recruit(modelData).role + "  ·  Level " + root.recruit(modelData).level; tone:"muted"; scale:root.textScale } }
                        Copy { text:root.draftLineup.indexOf(modelData)>=0 ? "STARTER" : "BENCH"; tone:"small"; color:root.draftLineup.indexOf(modelData)>=0 ? "#91d4f5" : "#9caebb" }
                        ActionButton { textScale:root.textScale; text:root.draftLineup.indexOf(modelData)>=0 ? "Bench" : "Start"; enabled:!root.locked && (root.draftLineup.indexOf(modelData)>=0 || root.draftLineup.length < Number(root.career.format)-1); onClicked:root.toggleLineup(modelData) }
                        ActionButton { textScale:root.textScale; text:"Rename"; quiet:true; enabled:!root.locked; onClicked:{ root.recruitEditing=modelData; renameInput.text=root.recruit(modelData).name; renameDialog.open(); } }
                    }
                }
            }
            RowLayout {
                ActionButton { textScale:root.textScale; text:"Save lineup"; primary:true; enabled:!root.locked && root.career !== null && root.draftLineup.length===Number(root.career.format)-1; onClicked:root.act("lineup",{ids:root.draftLineup}) }
                Copy { text:root.locked ? "Lineup is locked during an unfinished session." : root.draftLineup.length+" selected"; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Recruitment"; tone:"heading"; scale:root.textScale }
                Copy { text:"Swap one recruit between fixtures. Their identity, level, and appearance stay with your career if you recruit them again."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
                RowLayout {
                    ComboBox { id: outgoing; Layout.fillWidth:true; model:root.career ? root.career.squad || [] : []; displayText:currentText ? root.recruit(currentText).name + " · leaving squad" : "Select outgoing recruit"; enabled:!root.locked }
                    ComboBox { id: incoming; Layout.fillWidth:true; model:root.recruitPool.filter(function(id){return !root.career || (root.career.squad || []).indexOf(id)<0;}); displayText:currentText ? root.recruit(currentText).name + " · available" : "No available recruits"; enabled:!root.locked }
                    ActionButton { textScale:root.textScale; text:"Recruit"; enabled:!root.locked && Boolean(outgoing.currentText && incoming.currentText); onClicked:root.act("replace_recruit",{outgoing:outgoing.currentText,incoming:incoming.currentText}) }
                }
            }
        }
    }
    Component {
        id: seasonPage
        ColumnLayout {
            spacing:20
            Copy { text:"The season"; tone:"title"; scale:root.textScale }
            Copy { text:"Four clubs. Six rounds. Three points for a win. Tied titles go to a playoff."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            Panel {
                Layout.fillWidth:true
                Copy { text:"League table"; tone:"heading"; scale:root.textScale }
                RowLayout { Layout.fillWidth:true; Copy { text:"CLUB"; tone:"small"; Layout.fillWidth:true } Copy { text:"P"; Layout.preferredWidth:38 } Copy { text:"W"; Layout.preferredWidth:38 } Copy { text:"L"; Layout.preferredWidth:38 } Copy { text:"GD"; Layout.preferredWidth:46 } Copy { text:"PTS"; Layout.preferredWidth:42 } }
                Repeater {
                    model:root.view.standings || []
                    delegate: Rectangle {
                        required property var modelData; required property int index
                        Layout.fillWidth:true; implicitHeight:52; radius:8; color:(modelData.club_id || modelData.id)==="human" ? "#213d51" : "#192734"
                        RowLayout {
                            anchors.fill:parent; anchors.margins:10
                            Copy { text:(index+1)+"   "+(modelData.name || root.club(modelData.club_id || modelData.id)); Layout.fillWidth:true; scale:root.textScale }
                            Copy { text:String(modelData.played || 0); Layout.preferredWidth:38 }
                            Copy { text:String(modelData.wins || modelData.won || 0); Layout.preferredWidth:38 }
                            Copy { text:String(modelData.losses || modelData.lost || 0); Layout.preferredWidth:38 }
                            Copy { text:String(modelData.goal_difference || modelData.gd || 0); Layout.preferredWidth:46 }
                            Copy { text:String(modelData.points || 0); Layout.preferredWidth:32; color:"#a1d9f7"; font.bold:true }
                        }
                    }
                }
                Copy { visible:Boolean(root.season.champion); text:"Champion: "+root.club(root.season.champion); tone:"heading"; color:"#f8b477"; scale:root.textScale }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Future fixtures"; tone:"heading"; scale:root.textScale }
                Copy { text:"Format and difficulty changes apply to future unstarted rounds. Previous results keep their original rules."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                Flow {
                    Layout.fillWidth:true; spacing:14
                    Row {
                        spacing:8
                        ComboBox { id: futureFormat; model:["1v1","2v2","3v3","4v4"]; currentIndex:root.career ? root.career.format-1 : 2; enabled:!root.locked }
                        ActionButton { textScale:root.textScale; text:"Apply format"; enabled:!root.locked; onClicked:root.act("set_format",{format:futureFormat.currentIndex+1}) }
                    }
                    Row {
                        spacing:8
                        ComboBox { id: curve; model:["Flat","Gentle","Steep"]; currentIndex:1; enabled:!root.locked }
                        Copy { text:"Baseline"; tone:"muted"; anchors.verticalCenter:parent.verticalCenter }
                        SpinBox { id: baseline; from:10; to:90; value:50; stepSize:10; enabled:!root.locked; Accessible.name:"Difficulty baseline percent" }
                        ActionButton { textScale:root.textScale; text:"Apply difficulty"; enabled:!root.locked; onClicked:root.act("set_difficulty",{baseline:baseline.value/100,curve:curve.currentText.toLowerCase()}) }
                    }
                }
                Copy { text:"Baseline specialist controller · Experimental · No certified rank"; tone:"small"; color:"#b6a58b"; Layout.fillWidth:true }
            }
            Copy { text:"Schedule & results"; tone:"heading"; scale:root.textScale }
            Repeater {
                model:(root.season.fixtures || []).concat(root.season.playoffs || [])
                delegate: Panel {
                    required property var modelData
                    Layout.fillWidth:true; inset:18
                    RowLayout {
                        Layout.fillWidth:true
                        Copy { text:"R"+modelData.round; tone:"small"; Layout.preferredWidth:40; color:"#91d4f5" }
                        ColumnLayout { Layout.fillWidth:true; Copy { text:root.club(modelData.home)+"  "+root.score(modelData)+"  "+root.club(modelData.away); scale:root.textScale; Layout.fillWidth:true } Copy { text:modelData.format+"v"+modelData.format+" · "+(modelData.map || "Standard arena"); tone:"small"; color:"#92a7b7" } }
                        Copy { text:modelData.result ? ((modelData.result.provenance === "simulation" || modelData.home!=="human" && modelData.away!=="human") ? "SIMULATED" : "COMPLETED") : (modelData.status || "Scheduled"); tone:"small"; color:modelData.result ? "#a3d1bd" : "#9caebb" }
                    }
                }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Career rewards"; tone:"heading"; scale:root.textScale }
                Copy { text:root.career && (root.career.rewards || []).length ? (root.career.rewards || []).map(function(r){return typeof r === "string" ? r : r.name || r.title || r.id;}).join("  ·  ") : "Your local career trophies and style rewards will appear here as you play."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                ActionButton { textScale:root.textScale; visible:!root.view.next_fixture; text:"Start next season"; primary:true; enabled:!root.locked; onClicked:root.act("next_season") }
            }
        }
    }
    Component {
        id: trainingPage
        ColumnLayout {
            spacing:22
            Copy { text:"Find your next gear."; tone:"title"; scale:root.textScale }
            Copy { text:"Eight independent lessons. Every skill is available now. Training is always optional."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            Flow {
                Layout.fillWidth:true; spacing:12
                Repeater {
                    model:root.view.lessons || []
                    delegate: ActionButton { textScale:root.textScale;
                        required property var modelData
                        text:modelData.title; primary:root.selectedLesson !== null && root.selectedLesson.id===modelData.id
                        onClicked:root.act("select_lesson",{id:modelData.id})
                    }
                }
            }
            Panel {
                visible:root.selectedLesson !== null; Layout.fillWidth:true
                Copy { text:root.selectedLesson ? root.selectedLesson.title : ""; tone:"heading"; scale:root.textScale }
                Copy { text:root.selectedLesson ? root.selectedLesson.description || "" : ""; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
                Flow {
                    Layout.fillWidth:true; spacing:14
                    Row {
                        spacing:8; visible:root.selectedLesson && root.selectedLesson.id==="aerial-air-roll"
                        Copy { text:"Practice side"; anchors.verticalCenter:parent.verticalCenter; scale:root.textScale }
                        ComboBox { model:["Right","Left"]; currentIndex:root.variant("side","right")==="left" ? 1 : 0; onActivated:root.act("lesson_variant",{id:root.selectedLesson.id,key:"side",value:currentText.toLowerCase()}) }
                    }
                    Row {
                        spacing:8; visible:root.selectedLesson && ["shot-placement","power-shots","dribble-flick"].indexOf(root.selectedLesson.id)>=0
                        Copy { text:"Goal target"; anchors.verticalCenter:parent.verticalCenter; scale:root.textScale }
                        ComboBox { model:["Left","Center","Right","Whole"]; currentIndex:Math.max(0,["left","center","right","whole"].indexOf(root.variant("target_zone","right"))); onActivated:root.act("lesson_variant",{id:root.selectedLesson.id,key:"target_zone",value:currentText.toLowerCase()}) }
                    }
                    Row {
                        spacing:8; visible:root.selectedLesson && ["shot-placement","power-shots"].indexOf(root.selectedLesson.id)>=0
                        Copy { text:"Start angle"; anchors.verticalCenter:parent.verticalCenter; scale:root.textScale }
                        ComboBox { model:["Center","Left","Right"]; currentIndex:Math.max(0,["center","left","right"].indexOf(root.variant("angle","center"))); onActivated:root.act("lesson_variant",{id:root.selectedLesson.id,key:"angle",value:currentText.toLowerCase()}) }
                    }
                    CheckBox { text:"Shortened approach setup"; visible:root.selectedLesson && root.selectedLesson.id==="flip-reset"; checked:root.variant("simplified",false); onToggled:if(root.selectedLesson) root.act("lesson_variant",{id:root.selectedLesson.id,key:"simplified",value:checked}); font.pixelSize:14*root.textScale }
                }
                Repeater {
                    model:root.selectedLesson ? root.selectedLesson.steps || [] : []
                    delegate: Copy { required property var modelData; required property int index; text:(index+1)+". "+(typeof modelData === "string" ? modelData : modelData.title || modelData.instruction || modelData.description || "Practice step"); Layout.fillWidth:true; scale:root.textScale; visible:root.lessonPref("explanations",true) }
                }
                Copy { text:"Normal game physics · Manual retry available · Core lessons use built-in arenas"; tone:"small"; color:"#91d4f5"; Layout.fillWidth:true }
                RowLayout {
                    ActionButton { textScale:root.textScale; text:"Start practice  →"; primary:true; enabled:!root.session.busy && root.session.worker_running === false && !root.session.results_pending_choice && !root.view.setup_required && ["Idle","Career Ready","training"].indexOf(root.session.state)>=0; onClicked:root.act("start_lesson",{id:root.selectedLesson.id}) }
                    ActionButton { textScale:root.textScale; text:"Retry attempt"; enabled:root.session.state==="Playing" || root.session.state==="playing" || root.session.state==="training" || root.session.state==="Career Ready"; onClicked:root.act("retry_lesson") }
                    ActionButton { textScale:root.textScale; text:"Stop session"; enabled:root.session.state==="Playing" || root.session.state==="playing" || root.session.state==="training" || root.session.state==="Career Ready"; onClicked:root.act("stop_session") }
                }
            }
            Panel {
                visible:root.selectedLesson !== null; Layout.fillWidth:true
                Copy { text:"Help settings"; tone:"heading"; scale:root.textScale }
                Copy { text:"These choices are saved for this lesson only. Action labels describe the game's inputs; select your own binding profile in Settings."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                GridLayout {
                    columns:2; columnSpacing:30; rowSpacing:10; Layout.fillWidth:true
                    Repeater {
                        model:[{key:"ghost",title:"Ghost demonstration",fallback:true},{key:"explanations",title:"Step-by-step explanations",fallback:true},{key:"actions",title:"Action input display",fallback:true},{key:"timing",title:"Timing feedback",fallback:true},{key:"auto_reset",title:"Automatic reset",fallback:false}]
                        delegate: CheckBox {
                            required property var modelData
                            text:modelData.title; checked:root.lessonPref(modelData.key,modelData.fallback)
                            visible:modelData.key!=="auto_reset" || !root.selectedLesson || root.selectedLesson.id!=="power-shots"
                            font.pixelSize:14*root.textScale; Layout.fillWidth:true
                            onToggled: if(root.selectedLesson) root.act("assistance",{id:root.selectedLesson.id,key:modelData.key,value:checked})
                        }
                    }
                    RowLayout {
                        Copy { text:"Demonstration speed"; scale:root.textScale }
                        ComboBox { model:["0.25×","0.5×","0.75×","1×"]; currentIndex:Math.max(0,[0.25,0.5,0.75,1].indexOf(root.lessonPref("playback_speed",1))); onActivated:if(root.selectedLesson) root.act("assistance",{id:root.selectedLesson.id,key:"playback_speed",value:[0.25,0.5,0.75,1][currentIndex]}) }
                    }
                }
                RowLayout {
                    ActionButton { textScale:root.textScale; text:"Import permitted recording…"; onClicked:root.act("import_recording",{id:root.selectedLesson.id}) }
                    ActionButton { textScale:root.textScale; text:"Replay your best attempt"; onClicked:root.act("play_recording",{id:root.selectedLesson.id,kind:"personal_best"}) }
                }
                Copy { text:"Teaching reference: "+(root.selectedLesson ? (typeof root.selectedLesson.reference_status === "string" ? root.selectedLesson.reference_status : JSON.stringify(root.selectedLesson.reference_status || "Not yet recorded")) : ""); tone:"small"; color:"#b6a58b"; Layout.fillWidth:true }
                Copy { text:"Personal bests are your recordings. A verified teaching demonstration is identified separately when available. Slowed playback does not change normal-speed records."; tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
                RowLayout {
                    ActionButton { textScale:root.textScale; text:"Skip explanation"; quiet:true; onClicked:root.act("assistance",{id:root.selectedLesson.id,key:"explanations",value:false}) }
                    ActionButton { textScale:root.textScale; text:"Restore explanations"; onClicked:root.act("restore_explanations",{id:root.selectedLesson.id}) }
                }
            }
            Panel {
                visible:Boolean(root.view.latest_attempt); Layout.fillWidth:true
                Copy { text:"Your last attempt"; tone:"heading"; scale:root.textScale }
                Copy { text:root.view.latest_attempt ? root.view.latest_attempt.feedback || root.view.latest_attempt.observation || JSON.stringify(root.view.latest_attempt) : ""; Layout.fillWidth:true; scale:root.textScale }
                Copy { text:root.view.latest_attempt && root.view.latest_attempt.metrics ? JSON.stringify(root.view.latest_attempt.metrics) : ""; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
            }
        }
    }
    Component {
        id: garagePage
        ColumnLayout {
            spacing:20
            Copy { text:"Squad garage"; tone:"title"; scale:root.textScale }
            Copy { text:"Create local bot appearances. Your human car keeps its ordinary in-game garage choice."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Bot appearance preset"; tone:"heading"; scale:root.textScale }
                RowLayout {
                    Copy { text:"Recruit"; Layout.preferredWidth:100; scale:root.textScale }
                    ComboBox { id: garageBot; model:root.career ? root.career.squad || [] : []; displayText:root.recruit(currentText).name; Layout.fillWidth:true }
                }
                RowLayout {
                    Copy { text:"Body"; Layout.preferredWidth:100; scale:root.textScale }
                    ComboBox { id: bodyChoice; model:["Octane · standard body","Dominus · local preset","Merc · local preset"]; Layout.fillWidth:true }
                }
                RowLayout {
                    Copy { text:"Team color"; Layout.preferredWidth:100; scale:root.textScale }
                    ComboBox { id: primaryColor; model:["Blue 0","Blue 20","Blue 40","Blue 60"]; Layout.fillWidth:true }
                    Copy { text:"Accent"; scale:root.textScale }
                    ComboBox { id: secondaryColor; model:["White 0","Warm 20","Cool 40","Dark 60"]; Layout.fillWidth:true }
                }
                Copy { text:"Uses supported local loadout identifiers. Item availability and exact appearance depend on the installed game. These presets do not grant online inventory items."; tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
                ActionButton { textScale:root.textScale; text:"Save bot preset"; primary:true; enabled:!root.locked && Boolean(garageBot.currentText); onClicked:root.act("loadout",{id:garageBot.currentText,car_id:[23,403,30][bodyChoice.currentIndex],primary_color:primaryColor.currentIndex*20,secondary_color:secondaryColor.currentIndex*20}) }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Local career collection"; tone:"heading"; scale:root.textScale }
                Copy { text:root.career && (root.career.rewards || []).length ? (root.career.rewards || []).map(function(r){return typeof r === "string" ? r : r.name || r.title || r.id;}).join("\n") : "Finish fixtures and seasons to build your career's collection of badges, trophies, and styles."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
            }
        }
    }
    Component {
        id: communityPage
        ColumnLayout {
            spacing:20
            Copy { text:"Made by the community"; tone:"title"; scale:root.textScale }
            Copy { text:"Discover original creators and optional maps. All core lessons work without community downloads. Check the creator's permission and launcher requirements before importing."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            Panel {
                id: pluginPanel
                Layout.fillWidth:true
                property var plugins: root.view.community_plugins || {}
                Copy { text:"Community plugin downloads"; tone:"heading"; scale:root.textScale }
                Copy { text:"Paste a BakkesPlugins page link or enter its plugin number. Downloads stay in My Career's library; enabling them in the game still needs verified offline loading."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                RowLayout {
                    TextField {
                        id: communityPluginId
                        text:"223"
                        placeholderText:"BakkesPlugins link or ID"
                        maximumLength:256
                        Accessible.name:"BakkesPlugins link or ID"
                        Layout.fillWidth:true
                    }
                    ActionButton { text:"Check release"; enabled:communityPluginId.text.trim().length > 0 && !pluginPanel.plugins.busy; textScale:root.textScale; onClicked:root.act("community_lookup",{id:communityPluginId.text.trim()}) }
                }
                Copy { text:pluginPanel.plugins.selected ? pluginPanel.plugins.selected.title : "No release selected"; Layout.fillWidth:true; scale:root.textScale }
                RowLayout {
                    ActionButton { text:"Download to library"; enabled:!!pluginPanel.plugins.selected && !pluginPanel.plugins.busy; textScale:root.textScale; onClicked:root.act("community_download") }
                    ActionButton { text:"Check downloaded files"; enabled:!pluginPanel.plugins.busy; textScale:root.textScale; onClicked:root.act("community_library") }
                    ActionButton { text:"Cancel"; visible:!!pluginPanel.plugins.busy; textScale:root.textScale; onClicked:root.act("community_cancel") }
                }
                Copy { text:pluginPanel.plugins.message || ""; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                Repeater {
                    model:pluginPanel.plugins.downloaded || []
                    delegate: Copy { required property var modelData; text:"Plugin " + modelData.id + " · downloaded, not enabled"; tone:"small"; Layout.fillWidth:true; scale:root.textScale }
                }
            }
            Repeater {
                model:root.view.content || []
                delegate: Panel {
                    required property var modelData
                    Layout.fillWidth:true
                    Copy { text:modelData.title || modelData.name || "Community resource"; tone:"heading"; scale:root.textScale }
                    Copy { text:"By "+(modelData.creator || "See original source")+" · "+(modelData.category || modelData.skill || "Training"); color:"#91d4f5"; scale:root.textScale; Layout.fillWidth:true }
                    Copy { text:modelData.description || ""; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                    Copy { text:"Compatibility: "+(modelData.compatibility || modelData.status || "Check current creator instructions")+"\nLoading: "+(modelData.loading_route || modelData.launcher || "See source")+"\nPermission: "+(modelData.license || modelData.permission || "Creator's terms apply")+"\nDependency: "+(modelData.dependency || "See source"); tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
                    ActionButton { textScale:root.textScale; text:"Visit original source  ↗"; enabled:Boolean(modelData.url || modelData.source_url); onClicked:root.act("open_link",{url:modelData.url || modelData.source_url}) }
                }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Import a local map"; tone:"heading"; scale:root.textScale }
                Copy { text:"Choose a compatible map you already obtained from its creator. The app checks the path and supported loading route before using it. A Workshop link alone does not establish Epic compatibility."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                ActionButton { textScale:root.textScale; text:"Choose local map…"; onClicked:root.act("import_map") }
            }
        }
    }
    Component {
        id: settingsPage
        ColumnLayout {
            spacing:20
            Copy { text:"Make it yours"; tone:"title"; scale:root.textScale }
            Copy { text:"Your setup, help preferences, and career are saved on this computer."; tone:"muted"; scale:root.textScale; Layout.fillWidth:true }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Game setup"; tone:"heading"; scale:root.textScale }
                Copy { visible:root.view.setup_required || false; text:"First-time setup: choose your launcher, check the installation, then select Use selected launcher to remember this choice."; Layout.fillWidth:true; color:"#91d4f5"; scale:root.textScale }
                RowLayout {
                    Copy { text:"Launcher"; Layout.preferredWidth:150; scale:root.textScale }
                    ComboBox { model:["Steam","Epic Games"]; currentIndex:root.settings.launcher==="epic" ? 1 : 0; Layout.fillWidth:true; onActivated:root.act("settings",{key:"launcher",value:currentIndex===0 ? "steam" : "epic"}) }
                }
                RowLayout {
                    Copy { text:"Game location"; Layout.preferredWidth:150; scale:root.textScale }
                    TextField { id: installPath; text:root.settings.install_path || ""; placeholderText:"Auto-detect or enter your Rocket League folder"; Layout.fillWidth:true; selectByMouse:true; Accessible.name:"Game installation path"; onEditingFinished:root.act("settings",{key:"install_path",value:text}) }
                    ActionButton { textScale:root.textScale; text:"Check setup"; onClicked:root.act("diagnostics") }
                }
                ActionButton { textScale:root.textScale; text:"Use selected launcher"; primary:root.view.setup_required || false; onClicked:root.act("setup_finish") }
                Copy { text:"Use your existing signed-in launcher. No platform password or new game account is needed. An already-running game must be closed before a career launch."; tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Accessibility & controls"; tone:"heading"; scale:root.textScale }
                RowLayout {
                    Copy { text:"Text size"; Layout.preferredWidth:150; scale:root.textScale }
                    ComboBox { model:["100%","115%","130%"]; currentIndex:root.textScale>=1.3 ? 2 : root.textScale>=1.15 ? 1 : 0; onActivated:root.act("settings",{key:"text_scale",value:[1,1.15,1.3][currentIndex]}) }
                    CheckBox { text:"Reduce motion"; checked:root.settings.reduced_motion || false; onToggled:root.act("settings",{key:"reduced_motion",value:checked}); font.pixelSize:14*root.textScale }
                }
                RowLayout {
                    Copy { text:"Input display"; Layout.preferredWidth:150; scale:root.textScale }
                    ComboBox { id: bindingChoice; model:["Game action labels","Xbox · selected bindings","PlayStation · selected bindings","Keyboard · selected bindings"]; currentIndex:Math.max(0,["actions","xbox","playstation","keyboard"].indexOf(root.settings.binding_profile || "actions")); Layout.fillWidth:true; onActivated:root.act("settings",{key:"binding_profile",value:["actions","xbox","playstation","keyboard"][currentIndex]}) }
                }
                Copy { text:"Keyboard: Tab / Shift+Tab moves focus; Enter or Space activates; Escape returns; Alt+Left returns to the career hub. Controller navigation uses the app's focused controls. Gameplay bindings stay in Rocket League."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                Copy { text:"Action labels remain the source of truth unless you explicitly provide your custom bindings. The app does not infer your boost or air-roll button."; tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Saves & recovery"; tone:"heading"; scale:root.textScale }
                Copy { text:"Export a backup before changing computers. Imports are validated before replacing your career, and your previous valid save is preserved."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                RowLayout {
                    ActionButton { textScale:root.textScale; text:"Export backup…"; onClicked:root.act("export_save") }
                    ActionButton { textScale:root.textScale; text:"Import backup…"; onClicked:importDialog.open() }
                    ActionButton { textScale:root.textScale; text:"Open save folder"; quiet:true; onClicked:root.act("open_data") }
                }
                ActionButton { textScale:root.textScale; text:"Create a new career…"; enabled:!root.locked; onClicked:newCareerDialog.open() }
            }
            Panel {
                Layout.fillWidth:true
                Copy { text:"Connection & diagnostics"; tone:"heading"; scale:root.textScale }
                Copy { text: Object.keys(root.view.diagnostics || {}).map(function(key){var value=root.view.diagnostics[key]; return key.replace(/_/g," ")+": "+(typeof value === "object" ? JSON.stringify(value) : value);}).join("\n") || "Run a setup check to see installed game routes, worker readiness, and app versions."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
                RowLayout {
                    ActionButton { textScale:root.textScale; text:"Run diagnostics"; onClicked:root.act("diagnostics") }
                    ActionButton { textScale:root.textScale; text:"Open logs & reports"; quiet:true; onClicked:root.act("open_data") }
                }
                Copy { text:"Testing preview. Steam and Epic game tests are tracked separately. The app reports a launch request separately from a confirmed game connection."; tone:"small"; color:"#b6a58b"; Layout.fillWidth:true }
            }
        }
    }
    Dialog {
        id:newCareerDialog; objectName:"newCareerDialog"; anchors.centerIn:parent; width:Math.min(650,root.width-80)
        modal:true; title:root.career ? "Start a new career" : "Create your club"
        standardButtons:Dialog.NoButton; closePolicy:Popup.CloseOnEscape
        contentItem:ColumnLayout {
            spacing:18
            Copy { text:root.career ? "Starting a new career replaces the active career. Export a backup in Settings first if you want to keep this one." : "Choose a name and a match format. Your club starts with four specialist recruits and a six-round season."; Layout.fillWidth:true; tone:"muted"; scale:root.textScale }
            Copy { text:"Club name"; scale:root.textScale }
            TextField { id: teamInput; placeholderText:"Your club name"; text:"Northstar FC"; maximumLength:48; Layout.fillWidth:true; selectByMouse:true; Accessible.name:"New club name" }
            Copy { text:"Match format"; scale:root.textScale }
            ComboBox { id:newFormat; model:["1v1 · solo captain","2v2 · one teammate","3v3 · two teammates","4v4 · three teammates"]; currentIndex:2; Layout.fillWidth:true }
            Copy { text:"Choose four recruits · "+root.startingRecruits.length+" of 4 selected"; tone:"heading"; Layout.fillWidth:true; scale:root.textScale }
            Flow {
                Layout.fillWidth:true; spacing:10
                Repeater {
                    model:[{id:"anchor",name:"Anchor · keeper"},{id:"shield",name:"Shield · defender"},{id:"relay",name:"Relay · passer"},{id:"comet",name:"Comet · attacker"},{id:"orbit",name:"Orbit · all-rounder"}]
                    delegate:CheckBox {
                        required property var modelData
                        text:modelData.name; checked:root.startingRecruits.indexOf(modelData.id)>=0
                        enabled:checked || root.startingRecruits.length<4
                        onToggled:root.toggleStartingRecruit(modelData.id)
                    }
                }
            }
            Copy { text:"Deselect a recruit to choose another. The fifth recruit remains available between fixtures."; tone:"small"; color:"#92a7b7"; Layout.fillWidth:true }
            RowLayout {
                Item { Layout.fillWidth:true }
                ActionButton { textScale:root.textScale; text:"Cancel"; onClicked:newCareerDialog.reject() }
                ActionButton { textScale:root.textScale; text:"Create career"; primary:true; enabled:teamInput.text.trim().length>0 && root.startingRecruits.length===4 && !root.locked; onClicked:{root.act("new_career",{team_name:teamInput.text.trim(),format:newFormat.currentIndex+1,recruits:root.startingRecruits});newCareerDialog.accept();} }
            }
        }
    }
    Dialog {
        id:onlineDialog; objectName:"onlineDialog"; anchors.centerIn:parent; width:Math.min(640,root.width-80)
        modal:true; title:"Play Online"; closePolicy:Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onRejected:{if(root.onlineAwaiting){root.onlineAwaiting=false;root.act("online_confirm",{yes:false});}}
        onClosed:{if(root.onlineAwaiting){root.onlineAwaiting=false;root.act("online_confirm",{yes:false});}}
        contentItem:ColumnLayout {
            spacing:22
            Copy { text:"Are you sure you want to close this and play online?"; tone:"heading"; Layout.fillWidth:true; scale:root.textScale }
            Copy { text:"Completed progress will be saved. An unfinished match will restart later. The career session closes before the selected launcher opens the normal game entry."; tone:"muted"; Layout.fillWidth:true; scale:root.textScale }
            RowLayout {
                Item { Layout.fillWidth:true }
                ActionButton { textScale:root.textScale; text:"No"; focus:true; onClicked:onlineDialog.reject() }
                ActionButton { textScale:root.textScale; text:"Yes"; primary:true; onClicked:{root.onlineAwaiting=false;root.act("online_confirm",{yes:true});onlineDialog.accept();} }
            }
        }
    }
    Dialog {
        id:recoveryDialog; objectName:"recoveryDialog"; anchors.centerIn:parent; width:Math.min(660,root.width-80); modal:true; title:"Manual missing-result repair"; closePolicy:Popup.CloseOnEscape
        contentItem:ColumnLayout {
            spacing:18
            Copy { text:"Use this only when a completed match's automatic result is missing. This is an unverified owner entry, recorded with your explanation. It is not the standard way to finish matches."; Layout.fillWidth:true; scale:root.textScale; color:"#f8b477" }
            Copy { text:root.view.next_fixture ? root.club(root.view.next_fixture.home)+" (home) vs "+root.club(root.view.next_fixture.away)+" (away)" : "Enter the home and away scores from the actual completed match."; Layout.fillWidth:true; scale:root.textScale }
            RowLayout {
                Copy { text:"Home score"; scale:root.textScale }
                SpinBox { id:recoveryHome; from:0; to:99; value:1; editable:true; Accessible.name:"Recovery home score" }
                Copy { text:"Away score"; scale:root.textScale }
                SpinBox { id:recoveryAway; from:0; to:99; value:0; editable:true; Accessible.name:"Recovery away score" }
            }
            Copy { text:"Why is the result missing, and how did you confirm this score?"; Layout.fillWidth:true; scale:root.textScale }
            TextArea { id:recoveryNote; Layout.fillWidth:true; Layout.preferredHeight:110; placeholderText:"Describe the completed match and the evidence you checked…"; wrapMode:TextEdit.Wrap; selectByMouse:true; Accessible.name:"Manual recovery explanation" }
            Copy { visible:recoveryHome.value===recoveryAway.value; text:"A completed Soccar match cannot be tied. Include the overtime result."; color:"#f8b477"; Layout.fillWidth:true }
            RowLayout {
                Item { Layout.fillWidth:true }
                ActionButton { textScale:root.textScale; text:"Cancel"; onClicked:recoveryDialog.reject() }
                ActionButton { textScale:root.textScale; text:"Record unverified repair"; enabled:!root.session.busy && root.session.state!=="Playing" && root.session.state!=="playing" && recoveryHome.value!==recoveryAway.value && recoveryNote.text.trim().length>0; onClicked:{root.act("recover_result",{home_score:recoveryHome.value,away_score:recoveryAway.value,note:recoveryNote.text.trim()});recoveryDialog.accept();} }
            }
        }
    }
    Dialog {
        id:renameDialog; objectName:"renameDialog"; anchors.centerIn:parent; width:480; modal:true; title:"Rename recruit"; closePolicy:Popup.CloseOnEscape
        contentItem:ColumnLayout {
            spacing:18
            TextField { id:renameInput; Layout.fillWidth:true; maximumLength:32; selectByMouse:true; Accessible.name:"Recruit name" }
            RowLayout { Item { Layout.fillWidth:true } ActionButton { textScale:root.textScale; text:"Cancel"; onClicked:renameDialog.reject() } ActionButton { textScale:root.textScale; text:"Save name"; primary:true; enabled:renameInput.text.trim().length>0; onClicked:{root.act("rename_recruit",{id:root.recruitEditing,name:renameInput.text.trim()});renameDialog.accept();} } }
        }
    }
    Dialog {
        id:abandonDialog; objectName:"abandonDialog"; anchors.centerIn:parent; width:560; modal:true; title:"Restart this fixture later?"; closePolicy:Popup.CloseOnEscape
        contentItem:ColumnLayout {
            spacing:18
            Copy { text:"This unfinished attempt receives no score, points, or rewards. Completed fixtures stay saved. The next attempt begins at kickoff."; Layout.fillWidth:true; scale:root.textScale }
            RowLayout { Item { Layout.fillWidth:true } ActionButton { textScale:root.textScale; text:"Cancel"; onClicked:abandonDialog.reject() } ActionButton { textScale:root.textScale; text:"Abandon attempt"; danger:true; onClicked:{root.act("abandon_fixture");abandonDialog.accept();} } }
        }
    }
    Dialog {
        id:importDialog; objectName:"importDialog"; anchors.centerIn:parent; width:560; modal:true; title:"Restore a backup"; closePolicy:Popup.CloseOnEscape
        contentItem:ColumnLayout {
            spacing:18
            Copy { text:"Choose an exported save to replace the active career. It will be checked first, and the current valid save will be backed up."; Layout.fillWidth:true; scale:root.textScale }
            RowLayout { Item { Layout.fillWidth:true } ActionButton { textScale:root.textScale; text:"Cancel"; onClicked:importDialog.reject() } ActionButton { textScale:root.textScale; text:"Choose backup…"; primary:true; onClicked:{root.act("import_save");importDialog.accept();} } }
        }
    }
    Dialog {
        id:errorDialog; objectName:"errorDialog"; anchors.centerIn:parent; width:Math.min(660,root.width-80); modal:true; title:"Needs your attention"; closePolicy:Popup.CloseOnEscape
        onRejected:root.dismissedError=root.view.error || ""
        contentItem:ColumnLayout {
            spacing:18
            Copy { text:root.view.error || ""; Layout.fillWidth:true; scale:root.textScale }
            RowLayout {
                ActionButton { textScale:root.textScale; text:"Retry"; visible:root.session.can_retry || false; enabled:!root.session.busy; onClicked:{root.dismissedError=root.view.error;errorDialog.close();root.act("online_retry");} }
                ActionButton { textScale:root.textScale; text:"Diagnostics"; onClicked:{root.dismissedError=root.view.error;errorDialog.close();root.go("settings");root.act("diagnostics");} }
                Item { Layout.fillWidth:true }
                ActionButton { textScale:root.textScale; text:"Close"; primary:true; onClicked:{root.dismissedError=root.view.error;errorDialog.close();} }
            }
        }
    }
}

package menus
{
    import flash.events.Event;
    import com.adobe.serialization.json.JSON;
    import flash.display.Graphics;
    import flash.display.Bitmap;
    import flash.display.BitmapData;
    import flash.geom.Rectangle;
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
        private static const POWER_SHOTS_PIXELS:String = "eJzVveuKI1mWLugJnkPTcN7BA0yDFJzMZ4gf5mAWhALqDeqHGswKmVMR5xXqhxxkSZuGyGeIBBekaUaWUPUKFXCUtKxpOZx+ggOdUB60yyfDh2+tta92kRSXrJ6VGS6ZyS7b1rfXda+9LY47aTwem43Fvz8+Pv45S90j4qMpi9MMnymI//JXtU8oY8IX/JLxTr1fSN0/y+SHlK6CH9SP2Vgdpw+nn/ERRRmu7T0NNaXZ7iapVuNS0rI0z/Msoz/S5DbCr3QIb+EM/dzy0QChi6GvimKRHziYmdhKmX6Ko/AgPts/uQ+m2TZOZYshyWKFluJ9O0+j+HTKsmxMlxeOc9OJr4yD9ZtwPleffECuUZDvaZPGROrpzPc2XLK0tbtoEh620pjxkCexGuCg4ciH9HpqttfR7G7M3w1CJwhtG4UWVrhVsWCQF4vFwr+31SwRE/UUzHrez5KjkLDRa8ejwbqPfyLuNK00tkTBw6AND6WX2qSjTdEQ+7rvDgqCgL9E+O6JiLSOeB/H4L4olUVVMDBeZ7MbpRtpvvgqVmPigpGl0HR5rvVW/FsRP80JeIhktMHhi2EQErubNx2aQ/SXAcAICBUCXLiexWAYpAACUVUKkCzLohBHRxHrOVepypbVTt7OpUsJ/yEX5kOfDRyur6/T6zRNr3N8O004PgE+2xwcxIOxUJLQxKN5dTEW9Bu0bsbPMaZjzYkLPibLXrEUXGX5IocyqtQPdE9L8wKCyOjrplj4jXf6j4IDQEAU9G75SK+v8zy/vgYs9Omz/xO17yfjoZ7JeC5iROxu1ewWWfaaOvaiWixeL17zBgGAbq61D/Zi9+KV4KHB1RBDDAxpmxcDJAbKxsFYDAcjaT0bEj7HKGEbLNZWjAco/VTz90XwcLoYAdIvH6OYPZ841loGjNd79Z8sywajOBjFIzorjgfqEg1lR7qc+R2nacjdwtiILtEwh2g8zBPRH/GsxPEiHNI0YUB+Q/tB9rzNw215Lq0V0AFZaTVUlgPKiOiIVgxGAw0BqMXmaFJN8trbaL6SWv5ocwgbfopgxTosBx4J8MjTxOfaFxMXunAXHk1ZtoVD4gvreT65NVk8zg75Y06U5Eu2+mK0VFOujf7y+xl9ZceK8EgYj2uNh/StL629OvBo6FbTFfWJn+ZNONSp96ym2d/d+9pwNLUXy4fByH04W+4ppGcJIfkgcvA4DMan9swe+dBi/+V1qAG9vYUagxY02kgAoq/aoltyYZSa5a+wuqK4IzuMR4c6/mQ87KyJowysZ4u/NBkxbGlg/3bzBLe9LRLT7HtsZwweaQOPBvOPNI8nUtqBx29Jke2sffxlPKXm7D4CD4YDzjBRFEUiUsT1Ju8ZDzInJ+Li3f0IPH5bRAwen+nGfDm1cRwmlOKSNEkMOKhZ+M54+PcQ91GlF8cnSEwfny08+g/8ghRG0Ffqvh+T6CVyXVonv8nsFllowKDurPCgNEyUEh7cnKbzTpujEeSDAMmukGwW8zIa9DpjykP1uKyOVdz/O8qHUvJdackeMvrGuK78BOpSh8RCZ/A4Z5JCUQEUixWjYRAEAQuEvrOCiA29SvwzKr2ioiMG2Wx5okaz49+OoogUlgTeJ5KVH/F6/2l4oItzCstCwrCCABlaTB6NRgNhusKDx0nGYwzK9AfDCo+up/V11W8NiBdjnEJuk1vbr1RDJx5CwKPr99FwOAQe1p2hlCymAweRDyROnd/cFqv/e8ZCWhobfznqsRAuH/VWX2v6may+t+LhXsiO3f2jSF8FLQwW50v9IqBoc38ySWt/Uzw+H3V1+VY8nKGeRu9MU84zuleBIeHfMT7TQ2TdBQHxtQ64weFl+xN1PFn8/wdqNlrJgTlEqQbts7SLm+ML2JeM/KionzVsUo7IpgaXJz7ab6ivojCEkxnaI+VHkZdPbMHDHNp3GU6PgiJthoxNU0pE9d6DrTwKD2l/B6v/rvIBF4tR6TqgY79nuNPT8FBXpagHnhXjYSkrZxhFDhWnvF3fWNQKhxlbC+zor/XJDH2xDCL6jDTJsDiCrYxiEpFjSQ61WK+6cm9v0ndo3MrTegyHGbVC3RSFR9qpjj+RWD46s4P/9eyHYgSV7SFU7uhLTtLqYxqOc4yoWL3SZOjNUIo/DvzRjKLamp4rNPH49Pzl586AqijKCWAPnhWFKHYJ6W/vxU0Ow+eFytJznYoZ2XJ02RE0HKr6mhHXOtG57S1rA+QL5ZRP61XOcH1eKL4ccSabpaiRndENiNhy6WaZi+r9WniUdKioUY+dqAEuMfZ9ancYDKlJFM6gJqoHD2lQlKL2iC9+9CD4FyJ/3DgvisVikeuyo1MuZaUZ3f5gG0sXKY2WBCzSCNJcAoWTNyPPuA+PocSUgkdwGI84CgV87PkscPjlUaeebZ1fFIuiWJBV7TlDKzMUjvAeq1JJSHHNyu96pBExP6o6R4LDMiTItOjxm562DYNg2MCD/Px2DIFHRKV5aQp3ronFaAitd7QnJD2KBnqcqswjz/friugatB/ViY2uSIrNlBtmRd49vqV7vmuL5Jrqr9wDf5XW0seKmuK6U9JkqpTIb5QiAiHS+RfBIwxCXTjrP30MfUVeTShBvyMgAzoxAsx2hqCV6CelZgqr8L8Fj0NCaHHH0fgCj9EkcUrVjQI8fow42oROoBMV+zUcfr7R3Cqke8kf+eeMx5t6LqvolEvlezpdBEwYDgOTwrtxbMhdIA6iIRKaVo7fgiXmmikbjssGwvqGOhehf3KHnQbxZRAMAinDMtdp9hlcIYiZ8dw7FwvF12ODJsV0z38x3V5DIOiLYBB7VLNFjbEmFG0oZXUYYTSTF1oaQJ7eJZlzxagO8aCfWEDiII6Q8G9KgKhJLjHkPe2XwtVGcQwBjTjyVqEgciN8ty6mBbp6MY6zwim/UypJ9XQ7sjxSj3qZRAMFkxZEJY0aKJ0xAR7iIZvKbarNphpWqzSns5MEKoMFa9LRcPbCuCvY+9yn0XhkYwMMWzQbJ96yD5d2QurVZCgqIyVlTPWkmun8jfwKbFoeSMMZ8bl3KjVExL2aVmLuuB5ruSiM0oSK50zgzs6Q9si6bmvyLWST28lAFTSTSQByGITxpcsS3J/2cEN8PCz2WszW6BEMdLg0kbNDXr6JYzpS6mgXVHt8OrmF2e3qipJYDTx0vlIrUSNNSZJgTJFPZDuvGi9ai74z00aD5gQMUkJDG6E2akvuRYADCjAI8HBGnYahygbaKSJYLtK/LvfUvA1fvwRBcHmJy5ABNj8eCKw/KuvVS614CCqqX+hfIy7UIheY1JjM1ePZeiba4acYeLIwCiSsCEaDQXBJHhNp+v7xFpvo+tHHJ9dpH7k8wDagNHt4qXsHezFqHMjc1btKU3qbvd/7XUcT7ZLRoq8i2yFzXAb2vqhnqdO0WNBdTH7eaQhcJGukcTQcxDwUPxiNBhgCJkDaLbxczvWOdOvbUpDNoKp5VT183CGPSngOXscVvHaXyT6aKOmXCw8PMtxhwAG0ipKNFSE8wjBC2IZT2bVBsBClmTJmBI4mqCbgMQq4YmhIOACQWPBgCWIhaXtqaYLCRApBTDlTX+61i4+NMiu/u+MZO0j3XOscp5uLqVV4OOZeLK8Lgt5FdkDwwOXpJpdhEEBDs/9t3E3l3vFtjOp2G8O/isYK2ghwDAYDlBONOMLrlpC2nuzKtt8LjyBk9Hp/7xIGNya0AumWJmmmKoLdJfkQ7kco0U2ihHcwTDggEvHQuGvuUAXWaBTAuvnmxW+nSXr55Vb6eoqAAPAYBBATG48jTQhX8PHX485oXuHwEZ35JE80lOI0eFDPtqSBv/I/YEL+KZDgnxPIB+sb2iknENNxnUaHpm4ehoEg0pa10W1uebRWISFU1N+TACHXzvP0IdntBr4lJuDucrq/2hVhWON5nvZnSKjXk2wQQIyD2QY6JCq0TxCkuhKltXjcQvMoihp6JwSd+jzt2qtJOpruYot55CN56PGPnPTekxt4S/6CE0otpCyHYODaC8FDcBDudxt1NcsQeXAwwonpRsOh0WDtxPERnXsApEvCEfaphy7pOEtbN5hF3DT71RiBxR3PijaY3aOvWAV4SkDphY4+wAbJBoEFg0yCxXmZIcizoHjiOeqn9QIamjiMA1OjiOp9FKnq3UinzA/RcNjfeS8vKZ5DRNcuHDiEA/CO6/jy4R+k/I1ePBxAOi/ln9feHleNKyBUT084SWNwUERzz91dvJ/Ss9TDKcq1LqaSyfbdj8QF0LQDohx3YN8BB4VmHeyk5KytOPzDWBm7WryBh62v3EMb8Pm/6ziMlYJ/sqd0aENh4QiCXhZDr4zBliQk6yFwCB5K/nl4q6vHUNZW03k3MnxxVmZOkiTytCG865Aqizr5w8bY3qnUMvsttrlsXALfyX7YV5BDNL9V4kU4zzxXnJdHUUq6gRaRxkSViFil0noeGngfJUmYpAkzXl9aGiF3azA9VTM9yNqrIQlNJAaB5QAcIPi6AWeHItRsDwYDqC9WYEPgYcZj4ihk7eb0bxsPxxRaeDjAkA+Ejka4gQM2IhZkivN6NxszdYRhmABmtZWhIauP/pQkPPEvmTREyJY1Os1A4WNiPbqe+JFm2ZTxyLIoHneMpaEiPry8dDyzPpEJAnbbEBoiiacMij1Qqd09aobGg3jcmZZr4GFGRtXDiltqwWHhojdFCi4vL9VOtFOE/VLkJ4wiMpiGjWEYYnpSNAlDdFzNYIfZaodWHdQj9Rfqq2qzRTz03P2e0oXhcAjFPxoNhxSBj4ajZnzRIS9GPmjUSoVcOg+r4zPRBvjTmZiTMItdUOWPYYELsrRJEoZJCAFRE4lFVNFPHUDUJzoLTB3BIRy0+EgejMvSYDCiz8EAwbTH9j5Sbhx0Ml0MmSvRlcYaq7HeGDpPiYNSHbLgRzQMFB7IFQIPM5w6Ij3UAwm3WH0X7cyst+M8rZ3Jx1fc9+XHD1gJWNjJJK/rcrUv0zDEk/iag1PstiphEjzCiMVYibL13XyVz5HgMRqJL2nbB09lOc3VnYqiNfrHZgpf0eWVLwc7HIZhkkbxYMRlBepKISUw+JqEB+en/HGPeDi0ZlvBhrh4XFIuy3QUYgFG5uyGE9sEDxXrHooKGcMkDFd1nuR5vq/zMEksYbCv36bj5RIh/HBirLL02sjLjiGqgJU3AHCpWlgrMlsZdpCSeuI/Y63sUzCEMh+qyDQMo2RebteJ7ueqWeJoCCAjrM/CRuHQzQ27IDwDCRdpUAK2E1zMc1XmbI3w85iYiXc569BFkGqwP1ylYZKX2329r9IwSTQrJXfUHrXYdl7wcBrfeBDTXnOqkXfXq9Nxv9rWDqASQjKoibjnIhkk2FC68+39/TYJQ+XkatMUTmBihxQ5sIUGHh3RVWMvK71goOCQQVMIQpZnUl5p+CXbvtnuxIM8S3iVEIuy3u+Lui4FzOaxOlEpMq+aSs8pgVFnx3IGHfVTsqPYkD4x6Wbb+ckKmMME4SGFHjzCHEXTaRQl8x/v//NffoS+vgxcvTmZ3ZR5FpC/we5sMBqIV8LpkaayNY9GDR8MtCcSijNEbjul1uzertAhfs5ms4OwUL4OxiPP82lersuyrvdZErkzkZIEB/gLs1orTaZOo00Zjuub6T0j14t2vDfdjZU1cS0LVKuNR4RxWLoAqrmADfnwyY/39//5L/8yT7TNCCE6cRgm87vtZooaqzAKKeSmMuowjOb/XDqJEbF5AaoDyFpRvwgRE1peBvfPMErCCIA44ytKtyQTcL/cv3chub7mz9n1LHGgmkzKMs+T+fbfto91/aEkeIjbUpaRp3nBGw4Q9BctICZZcGjPxpL6sa6bg6nkPq/zkPzojl23P8g245nFZ2ZLRESuh5SDBVEmkpSU97/e39/NkywMszSMUlTaUjSTlHd3m3lIJSFRFFwCD2LwfL2dh5zXvYSJCNlDSRJwOby8pOPJKDIeSTJhPMQ9RadGXxA7IHlE1Z+vk/n7D8BD6Pra+osV7+gb9hBIZZ7Pk6Rcr/fr3Z6yRAoPWqOC0heCh6SRNNHtSL8oZWb8CAoTxbKbKk/+mEyAGnPdii+aRPaNtaox/770BJReQt+lXcnm/v7X+7skCVGRE8YZGAc3K5zf3d//jfAQTUkxYUj75yEBIhMg0L/CcF6WeSSdTXmauMEsnyU4nPGgbl3katCG/FsZYVOZkeX7/fvlMl8y5XnOSPD3a3wXSBQeYbLdlvO63JdJktrykaBoWFclY//cjmGiyWTCTIov0TgJ/DUezFM8h41HOJnlbJuVYnBI+UIyXEsZnzAhvagy5gQDzpQAOmTPCwY8nGzv73/9dUsdRXxjABYFwfz+7v7uJgyARxAgp8V4lL/e3wkeKiwKwjhMNptNHoaRxiMiCJLlcjmbsLKKlUYqwThPz08Yq9lyudls7rab7fv379/XdV3z3xpbG5vKTVmWyzrP51GSr/flNq+nF3I9sSKJZT+yLJ3Nb2YiALCXUTgBIKqzRuD0zMIjgkczu6aSI1EyMCCT2c1yJvkeHcDrvi9lLCofTHEqcolKiTnxgFiS1a5Ko2AQD4IQePz6669bUi5uMJff/+3+/iZ0hvzOgyDc3t/fbxI/sR7e3N0RHqEkIuDfovGbX97NJpIHgQC04kG/gX2zvFxuljcAcU4dnaUiz6+Xy3LpEvDIl3ANk2S+q5N9CeVgjU9Qf4eOgmuJ7j+7mSXUFsSdcUT2SNJWKVJTs+XNjANRxmOSXC9zKNvY4BEmb99tZjCPzOC2ZJUlBwqtxkDEhf4WVw8PhZIPsBd4hBG8UAvAcAk85mEwODeAnAdBsr27v3ftOR3+7u7ubkmGQoQYGcRwstz8splNEor84Y6iS07KTdNnYn11vfx5WW42y9lsU0IIfq5/Lkl1ETJagwEo2jGb1XmClMm8LPdJluvLajyuc9pJeLy9uZkp+QAAy+UPoqAQ+8xuNpubiYPHbLlZQoQshz5Mbn55N7OZjZjNMiOSerH9T9EiDp3Jx1kQZYvHWvOx/PXX/wQeafW4yywhCcv7v/3tfhbGVwgVB4PLAfTVICQ8bhrDgeHmFxuPgBIScTh598svv7ydRFB66G/JBIiUtfFkjUubpNfJdbmcL5ebm9msJNLst4kWsJ3N8nyWJ5Mk3+ZhNC12+zxM9DCP9p0TcsjIb0hmy3c3M/agaFB7tnz3w0QUVBIms+Uvm7cTxos9ockP7969hY3R80JGcTj763/8lfDgWNtOCLEOcrjfNWrK4jEKzs6DMCsed/rUH3/99f8lPDIAYp2wZDyq2++zoYQfAfC4u7+/v8F61x4e/3F3twwdPC7TcLLZ/PIL7AfJNrNnlmzeU96aiy8MMNfXSb5Bl9zM/jRXFh+c5ak8tNK25vR1Qs7vJEnKut6u99skyUnn2epPXzwG+2/e6f5P4f/1O8aDVf9k9k7jIeom+WH5bkY2X6WwglDjwSBQ5aqy6gJQ38j1RXBxcREE+Ecp8/Pzs2Bxe1vQHfBvC/n4MQmztHh8LAx/n93c/e1vd5MkrR6rF6yuvgYoyd39f97/WD4uGDuFSri52+w3E7gFutILDwmtM0smnOabJLPZzc3NbLNX+ULTm+G/Xl/PynyzXEJfzWZc3G0fwCsJmz2zZDKB/5aXm9kymdHyzyJyZKvEZRZ1NVu+29yIPSdb9cPy3Vswm1Luk8kNiTIHSrALaThZlksSBQrjEQ4HcFDebWbPVPIxyFd5cCF9uwcHdmv9fcy9+HVmQrX/59df/+2+DCfp4vax4t+HFDgAj+0kCVePOwgIp9AvWT7mSf34vSMg4eZuVu5LgCQhOfvT1z8vycvncCeZzZZNPCTmu07y/Loks3DD7mzaT4xHXs6S2eamJDywwi0rqDQFvHQphce7d+/ezngle7rnEts5tsPLy2QyAx6zIkPimiLiCZwB2Cd+lAB59nS7vNlsoJdFR+0KRMEqKrY5oopvRI+RFSJFpc4NwsvgDALD6uuSdFDx4cOHD2UQhtliMR4F5+fnwWA0gHzc3939GIbf1bsCzhhpq0FIeNzN57v/tYgQsMvNh1F5l8w/QOEN1GgN+4k1HihNOeZK02sY4XLP/r89Fou+n+f5JpnNcxKP2ewAHOk1zNEM9jqHjqNLSCTPam75w7t3yx9EpGazzf9+99d3ssV4LJcbxBJReJlMEsjHpi7TeDQkdyRKknyJ5hM45DYFUb6fJZslMnt49CgKdxXCd2wgPcTpb9LtmNtA4bvChxQbmK+HVC7jy5CUF/YGl3Qa8Hismnbn2XJ/f1+ClYktaWGC9OO82GVjWtxMABlG5XaW74sYa6aL+qXEV1KXsJ0SAieMx2bfyBwCDcaDtAy8MCUfjo6i+Y1quU5WV/kkWb5fbpIEr3OgJaD5zAnw2Cx/EFxns80vv2zek7QgBCXzvtyzgxUl4Qz5iM1jweoqhI2Z5eV+myVIvqrRgnw/n28VHhD5rIBbChYR74GJcMoZPFTByrPw4iLEP8paQL2Tvw5OpSnyHPmHD4+PtY4aOQOAU/P9/YdtGgK6KAKMcpf6w+M+D/UoqaJyW66LKBiiwJpaTx5VmFfogNRy6s1vb96+fQuueHCQ35Tn+c/XGo4ZJqz3rXIL7xkBRpJcb5YqpOE1uenn2Zw8KhG0JNlsN+V+yvEH7Hm+vFm+Z4MShQnhcfO+RLKV8jdJlJd5SfLB+Q4kgpJ8WW7zRnShvVw9mBgeIMrzMMHPCSekKyaTfP/4+FjTPkoXcESZhGFe7z/UOWJ5OHo0RgA5DuvHx4e8eb+SBiAw4kFDXIJHVNb1Ck9HsfBkNnsLenc3a4GD6OdEkiFIkfQRXF6Sj9l1Mltu8pKSIyRNKhczg/fwVmVWkmR7t5mXUxQLUL1nkpfLWW5KPJf7/d1sjiScKrpI4HJTqk0yhOiY+XZbIjGl6Rl1cw721Rcem4HKU0M6lCmlNAS9mCWdz6fTPC9yBLUq8i0Ra9XAI+ckt2hfaOY0L/f7Oo8v4blbmeW0fnh8KBhLHXQh5n6///ka88svL/+J/E1KgKTlvl7laXiZsrND4vH23S+4m9JDSWqxnvDI89kSGcNe44EQBCoFMfhyu1R4KJrN/jR7+/avb98SINBSSb3fzmZwihmxJEcqh/QVVaWX+w/7uagvHkCCK52ENI2HqqOpb5a7uky5f1G+4RoxVUsNjHo4VrLyegO1h8SCY4A8zzjRJ0FY+h1X01HH4oQor98bQU1bHmmWTadZllb1rgITOBjQPCjr+mdTAsaaI72+Xv78fpVPuEzs+hrW4683N+9+WSI/K5EdoaFeAvBzms+SJRyja8+9UuHdbEZA8DAJ9/35fGOlYOSyy9ns7fLdX99BQvg+9cM+n3GlGppNQb65SVI+7vdLqjukp42zNC/r0n6mLE2yJF9VuV33LgcoCFhmJgKjqDQSQCVPMN8XFw+3cZgiqX5bfZff3lZVtcAAapD9tIgX3y+q1WIlK3jI22QySHUMG0PhEq9ZasZgkogXAcGgijOIbBQrTpM26QEo9GorjIARvwZn1L+SdBex2tdQZf3+/XbP2UVKMG7v7rbv32+Ranz/vlS5EoZZZOR6uWThS/P0utwsVR9ShwronIsvcY0ETYUzFVDlCs5cWa/hIktvnB8q5A4wvx4PyRWfqQQC6YJqGfM8L1IaBg/SxSKFH5sXi8XtQ86FidVtVT083j483hZBnAXZT3/5/vYRL4F8rOglV4vF7e1PVXV7e7sDZTFL0qKqFkW939W3t3WRJPm0yIqHOi8qooIEPMuKim5WFOx1RNmqoHUUFkWRBkH63Xd5OoGiwvhEib7nlVnmP8NgLgEIzDkjSFWZ83K7vdvv3+8Nme8f7ja18Iz1LVwB4iKjsVqkYU6ZlzSnHoxeTb8klNfJ87yqyhyaPM3y1Sr/DnzIM5pPla8Wi9VqVVUryEWMlZHw6xhwvFq8qqrqz99T4dRisaj+Uv3004KLc/JVnq2qalfv6lxGAuvbalHd3u5ub28fHyuM0gZRVi0WFdj/WEVRFuFNTBXB8VjjNkW+AIMX/4pzHh4eCp7yE3/3U71Y1A+3Dw+Pj1VKA3EFuunDw8PuAZeiku3FblEsauBY0GJ1WVVX1e3Dbne7y8N49a/1Cs8MFkPBrRrlyNdlkm/quixLjYeyB5u7zd2HD/sPBg7GA7s+3P24hXxcw/KJ5ijqCstpgKrbXZ5Wu7rePz48VpDzbJWv0PY6RyonXVUVnuuxLpclRn5X9cPt7cPtisR6Ua24Az+saMR7sVj867/Wt4sooA303IpG+RaLbPHTT7SFaDBb4M41fs5Yr0DzvP6++vOf//KXalUt4igqgBLYVFVlVeJ7CCVVVFVd76qCVwShHs5dokLraa4DrUOOXYALwl2UZVmtSvSbFcuHrLVCElrIACRVGxdFUZYYF1ysljDBYJonH+Ji5PWMlDbkw1NXy81mu3+vab9/z+Lyfru/29/dbXP2R+B2wbYlOUHPcFe4e5bnRbla5WRI0zwvV3W9grQEl1lRVKQEGY9VSc++AsTE14Vs04I4GfYUeQodhaU1VrgmlTFBcvLFopCp23hNG1Zywo4IQ0oodEInffX6VZZNs+l0WubTBMokm07n83k+n5fTJC9LwqHM5/kcXJjyy8JSNcoL+ZhCHaVRQkYd7N2U+XxTL+mZU4TFbDNn15MJ8lUcKnMi9k+wwOS+QX3M3i5v5pK1dX1aHLSZIaEIT7ZhPyjZrgdBMNg3n81mS7his5ubDZwt3A/PhYvJIAnSYZvNhk8kS8+eWwLvCHEImTplRcrlDKenKQIKDJqqsItCYdrBww9wa5FO5sFxDiNcwlouyq4GQXQRXJwhiDs7Pz87Pz8/2+/2+/0O/+32+91uV0PUWfjpY1fXWxpy22zhdUNUikKrkqJcr9fEe+wuy+12e7O8WW63dcmsZdZfz/70Jwo0JHVBfs7y+ocf9PgqQwNvl/LrymWagbVw0sG+bZnPJmFy7bprSc6pKUWAD9gjkzj7nzclD6qTK8AXvcGwFrLFirCJ23MMhvTUNAmDC470EFgWZZlvNksAggGhokQsi6JaSgGjNCINYky/jIIIGhslA6qzlCU7sQQLpZR1iM2j17x0hEZ4vwcCyv59eNw/Pu73j/ud6OOHR4Kk3q7XdU0qiOR3XUNOy3K9LtbrcvVzTbYB0O5/3O9/3O63OAMxDYardcDJo2b8wXtUsBSG4Wy5zJHFxmgIxeHzmzlGUsHQ5ftl+f59uZyHFJ6LQb+G0gM84iCT/ySj6MmsXC5vNm83N/MZ0u+z+dxGjWVlPodTDJZr+4JeDXOO71Cp6Gp5Uc7v0R1pkDdJkimtHUdd81WWJUmSpRmtbZ/lCS30UhZlVbF6wZQoWlQFqgtH8uIwosMTApBeO8Gk8YD9IzQeHx8fHh+RTvyAb/tHSMluV9e7uq5qfKnpew2A5EttACn/bVuwqOGndbVeF/Cl8jybmslYSZZk02k+1YU40FFUo4AuBf2TL5clei4EZDaZLGcoZ6hrGYgiff7zz6TaKV6w3F/WR8vl5v37O9Za5CWTCl2iIgtSvoZg1/v9drslucePpcj9PJmqa4HQr9bFfI7CjHyqMIJ2h4LHMnK6bIu0O86q1lVV4VaABHwn4vnPXFtR0CXyBGjao6JGNCyPkdwqewfzV4FQrde4H32RPUJ1vUPr6eAdHQd6U7QRPapwg9nURsgW4O9m8/69FCyANlsh2az9M/QGbIthL7PYou16vd6S/IsyViqZeQ5ao0uhvcRcUdjkjdBDlCU6WwZLnPMBeDBi0brE5STRCceBSopFt8uZ7FvotUMVq6lz76yvpKaEFGNVmxuUF9mrV6/w7c/ceMXzN2/euGigEdLtgMZWA6GuxMu7zUEw1TdL+AimZkF/IytAvMeQOaGwKUl6DCB43OWysHmQy9Vz2Of5fF7M5//cfB55CPtRBIdXIFmFTnOVpAV+EfkM+DJlpQZbwgR1kGuFYGEpkKi5VbrD2ywnS11Sl8CRUyG24oXXEuE32omPdsAMHoDBvpsNhjqAd8IYkiTcWZIgygUg2NucditFeizKVYeXNns37uhfQm/4sexn+uMfp1rrAgAPL1ksEPqI1nBUrJvKdHTOJGIDSSZe5o2+8GRpS/sRpLhePoXFwnmEAdxzLaeaY+qpFBKauh7NdDV9Xi+x98Zw3AGQNtbZjIfuLkuov+V8fnNzg64K7cNSovhm+pOBpBUUfhgWBv3Vf7wc2VhhLKurQm0qm6H5g0/eZiQVSsb1VQlloimDN2VpU/IIeqOsQIsZ0O3Un6/Qoul0qlnmQEekGmNjrO+ET3QBQgMKjehQT6YfyRaLkGw25RI6yem/pKuEqOu5GsfgoNgHBnqkGu93PDplvV5L32Z90jjL2kW7X7xo3sFiPUjY599MXVedJF0HeBew2PqOgsVaYIQ/zBfxG9aAgyCxmcymmlVQi5L3ifg8z0sLQ9oBr8g+jLuvZbBbSAsGDm6BxTzIVBQO9gg/lNJGtP3CIRxBb7UZv3gxfvHiBV7/xL+8ymhz7DckQ1dX98yyKbcIt3LUkm4iVKjdv8iZsrhq42T1rEb30s9GD0cbpAvIsLv93Chp4ik7jmozL7ec5q2R5NzWNQwiC2NOJpW0M9YBh4IRb9PqZ0Lcb81jttH0j9Jmfq8WNxu85Z+ZS+q9WwoRtSFv41KcxCddhSXT3PiV4Ey9woXAIDGdvtB6ck5q3lXFCkSrE3HLrauIWiAf0e5s3nISCg9Od4CxzFZSeHxAns/Z3HF8nufz2Tyf4csUxVdJniURQS1DnTwsQJk1XhZJR4nTLKMu3EX6LVqkId5AizDjFCINXBUcY4kXxwLEK4bF4PRi/Ir2+UxTyDLH+Iov2kjMnHLMyS3ARZRkCqkNdW2NNl38VTEtCqgi0/9NvycwICKwJXmZJ/iHyHqezPQgczth/BxJiiLgaMv4nRRM098swUASIRTKpBc1AyNNIuRS4QkUhv/CfObOm1dsm1+9Ur2dH5S7ovX+syaxpuogrUVsLWS+ObLGCk+Ex/GnLJ/Y6yatIma5Y2S21+vS1WlZzppKp8nKPLlGppYn3tBANA9Hq+QVcTwv6zqfpHk6oRLqMH8oJRnjZ/UoVZjl5UoGZMS1MWOOPDWkWK1WSFxTSruqGBw2AFEUvchevOD+qt4FqMMTpcE6Ja0PD1sZKcl74Z2jDuDbCF4aT9aZ1C42Vh1Ci2MEWCgGAMIOGMysCnAMieiVZVXVy/rh52skVZA4p3JfImQIdSrx5/1jjazyhPl/kT8+pOEzHg11k6yYEJPmZVU/1rk9dVZWbZNiUf7kEVB51dZiQUvGyiFNftoquZXhJB3Glgw9EqPfsDuW9Wm/rDFN3hnsPIjQqjboPmTwoPuy4SaTwB1SZxAEm6LAUGNZ1j/X9RLj7IyHIa2gWGropPSaUiRh/vCwlFFxTp1jDFiGt+VOasjbTOYw8qKwodI4mXyUfV+9ioe8TsNwGHmsirFDd15+epqxxMPWURx38Zb3RcPOnw7i0TxJdRDX7nlkm/OM/IKGEQQliE9JzRNIlPtJeGaaX6RFeFBBDc+AI4iuc7CT095cXeC86UFqp8zcIZ7qrtKsau1IVG7wzDQaMhpjwbDXY7CXezPj0WSMKyRmdmcrRx217v/omRDZtLRhywV/97vx+Hf85XdKMOS4Fr1l7k1+2FRcHY8AE1wf0uuSMaASN04G69EPnqhmUvp6GAiykoQoUaNF24jXqEeQWbMYSuLVH3gogibAs2LSq9jQBhUj6OUDxkMsdcDioXmrjAqY3+aQint1kGxW8am/+x11XcWyHrvTSq0aVVYLUuVLePeqBkT5LOYFufJJGi3C3GuVuOHZhFNtc3EaF09Lda6UrtAXcaR4GIOWcrZeBSIv0yBG6xdqyHrvehxCrx9JrSZ9M4SCgvqJXrzQguHLh60G8FzE1N8JTn2G3Jzf5Dvrsmg8FrFkBeibHuK9q3KjCEvNRJbOk91KhfJT2hLtik+PoivyaFpQjJAmqQRyDeKVNVQGCBKWYxRbTWwu8sWCR/Zp4LsoqhUqK4i4ikI3UjVcbdJbfG3+MInK4o5GxCLh6x/fAACjJr2Irq6u/C4unI/xv3qD7agBRkTm2hbbJqRo6As6QoMBYQEiTZPiwmNJkM4XcMrAjTQ7cVGLlFU7KqpQVAAPcWBpKEFG1Hb73bZEYAm1JWCQmZD+w3LOT4aHNnzCIa6QiKKn79KXLWKzM/zvL16YK3sk2DOCrFfGGB82r9luIY7x23Wa3Txqq95GP2Jh0JGiD4mDjLL1jYi/jVqkaqpKvox4ZgWVLlkDaQCERt222yITINls0MpSNk/VVyUV+snEiAg/Xthdl6/jQjIcgtPCfnnj6Wg0+qaH4Uab+0iwzW71BywUtH6FLaB9cjI8Dn0h6fD9qaJMkmoO9xvr9MHO+PqzsYONNCrSaJAZY84sHzxKWlec+SSjP4TJcJSC9R54pWKdR27EE+7pcvtoOHTOfGnI4V/Dw+2TD9GUKjHjtUzJsH9RPlA8YpM2ppjSZDs53+KoNKOxsF+/QMnRW2r8oA8PtRgP0h0li0eJnCQNHm95HHpVFHiNC0x302aa6Nth3AtWbl1IWOLRxkoG4+rq6phY4wAmDhb8uKov8KeVT9C+s3WKzSyPeewPwNxApypXq1UxdRAFnXLjF2oRHprAhaZB8LgyoYCiSjj8JEVGtYNN/rpPD33FeusQD/lxyGfsshpEfWDESkD8INx4TnQifzT9L9GzbVeW+mtzYHOJIqdP9/2qKXlh6SuVBUCKhvPnVp9BhM0zmXiZm3FGpWSoDFEmxXgBLZ7M0SzUnQ15EtYbUTRSdgOc8wTCupHjRkXwruJXdL0+jUjcxECKwkO4QReXPqrUFOwW3Ui/s3s0UsvIOWGsD4dI3UcRxwr03LqXMSbUYHk6nuqKpK6iBa9Wp+6snpgX0mNf3yCCft+BiZWvUo8zIkA4KrPdA/KfBQp3LSHEEdF4OP4+s+yQtN8i8zxDtEhHetrWkQrGEZr/r2xvQkku6c7PhEe7JDMvHNHnzJKwl56G5s8aTFa5eh2dg4jdG43qEVvZgoeLBp0Uj8cvyam1UBJdqjijEOHbGt7bysfqT/LozdsDDNzCbndg8FAdA5/iTyjPQnJtY/RlI1ycKVa9yRAqMk5CxHpoo7d8Lsu1AUldr5Bt5zmiCpEWVKIIVqQrNWG7/qoZWCRk/JIeCT6voXH26rVSG7rBjduZXYCs1/qTj6FOVM9sQ6E9CdvFM44eX1j9kfbzVcYSQqoVKo6VEGVoYcu5awIPxkQQdp5XJulHGcBA3LhC5U4aoQidZ6DysvWyAqh+Vlyer2lb65jtvegs0w/QCjEOcjyib15smjueLVI2FnK+3a3aYNBnql4IiXDPeHn1+vXr1w0cbK/b7cqOKHs8d3RrHyDWFdzFqZ2zvU7IiySkWaGSKVwEgQSXHI/FP+kw+itxittA59ra36V+PRqNoLZtmZQp4uK/+Vb+KBKf2xF1Vo9kGijclHiTmA442gEZj7/xsNBsbTDbWzevB5PG4b1WSAsH9Xta6gsyUaCCvFpBg61QTE05yTaZssSFAWgnUWtX47GdgxJgh8PA6pknwCEPayFh8HftdFMxOfT69esrSIfDe7t7t8XXDjScEOs9RmTc3d2Nh1rKQFQXJuVAcXF6BcsuIsWlT2kRLQ8A6EcLnmjkyod96DD4iDjQ7rSO7yWyCO/h5ctvQZ04WL+Y7kBskvFKNuZtAuIt8myvfut9t8mTY7vJTjdXLq36SshgphiXk1c1onlqnAS+HgINQRmynnR2KaNtHxUMsyxS+upIHFr4498brmT89OlTYjqTIw7/4zX2G0C8jqojJIqtvdvZYXmX+ulc/v8A+euCOPgQJhy4U05YQUKoNM71rtt2tyYew2A4zhBkHAbBgGESzB4WiHHEgCsBsMjC4394ksNBR6sU9PNa7VPv6HFkgZmigxz7NP30uuk6L2JbD5exeJGuQKKDE664jJDIabxqRuRE2ftW/G1o6BMHjoKDSOi40RUGSz7kTdmjUfz85cuXEI2nT799+vTpU5IDcJ6up3CSfQTG4ThPhrfxcJgtHJxMEre5estmtulbbWc7LB5GMc3wVKCsC7VwAHcNOMr64p6gqRs2RYjDcZYYg4drz3VFSIuOaiIC+zQGDIQCIaKF4Ntv5deXL5/zAXQQqSr0jF40hhoPLOukliz6OPJYoJwau89aKxN1XIMmMxdVtdNyUtJCpVRDx6BQu/UNvQYIwGa/ERce+msIhXzJbDC8nIkLrSLhNMOCrW8hJEDjKTLJL18+tY56+lIlszzyobfwuMT7oz8ChVZU2m6umdZxKfkMkR0wmosT9jQVEMPCEsartJhoO/cmrtzpIyG9HXDoKK+FZc6l6eW0LiICB38ZjUbfIq8PmNQxUGs+Gl0SoheGxAJBWKLtdDz8NpueRP3SsRMN/Hxk7Qie0iqQkRVN3oSNR0mw6kuthqOjWSozq+25q62srGf/0zIOFhbM8xELCf1Erpb6Ccc9f0nC4ckzRNm6oTIfZkW0j1RXPj9Mf+QuwfeW3XYL2i9jKRsFiR6PpzA+wWT8LFZj8OQodOPhWAGFh2s6Om2bTwNXJrS+Gj1lS+LJDG8/B2nhOIWxH4eHuov9ab6TiDgM6jIg9sn4yjYiirJ8VWHqKq9aAb+LltNRy+wYQWltmcFEZQq9uFyWYz9MTR0lcLwGGI3f9Pbz58/xwhwtHL7c6grbBl1+FvlwOyrLd7ta807XoDRVl/jBspIIdBfEhBbS0VloP/o317FG7vQwmgZD3bIfE36leSseo5dPoaRe4hdHUWk8AIfWGdY4j5BT9uzcFP7Y6Xh4oPg8ETw6YfNhkmDEFaMoSgsq6Fqt1JTksgAkqHd1E4umQS0tNEUHKl15BBEY7C43lJXF/acvkTt87qLx9OVz+Ej2E3oPbFa88+/Lrwr7OOrhMPUsr67HPaS1i6vBXk1RlnNpF1cS1TtkIWmtdR4nILXlnmL1EG3BYLz9jtNHlj9lc9+x5+ziknQ4Bz9/jm2vIR41XuCjb/yR0YfhaetwkgnhLe634+HxCe6peytUXReUEK53XEXE1UMIF0V1UQzT5zQca7x51fymb9u+TXA8936EIRdN1YNHu/FgPJBT6GV7O/VFnCTofs6x53TVckt1OZDgNVgFpEMvp4DUCuSESoSRC5VVqU/zZhpgnItgOFGdwUPtkg1LT6nfLLfKsZe+p9vBbeFYdCL1ImKkRPKOrYnHtlPa7OzQhIsFrclm1nWhuVVKdWGYkXTXxwJyLr6tG2yM2qnlJwXVoJlD6OjX9OT0q3qvUhzHzz8ej+Z5/h0VIC2ItJ7Kg4JdHFN+8A56C6vu7ChyLOhte4CEjDzlXz5CTHyb4YtFk/dNOJ5rJ5d6l36uY/l6LB4dOqftPO8InQg+DhC/Y7VAwqvLGcUlUxClGsMqQDspEmuCYfPb3RGrpGHjFKvnHQvBZ8GjW0L847UdachIx5ken1q4GmU5BhYFEVkgqSqxsi7HjFYLjkRDMXbQ2vUdOJ5jvOmKAWEzM6L449tvv/3mGzytydLoZzoSDaVPPgIPl68+j/U2nAVBhFreBYfaIRLe4JdlV8hw57wKJbAQl4vWdSsJC7zbXLdCen+XD3l+fv41M7xTT7Eievlc0KBiBY6/9UGcc+cHPJL3rUxW1WFHHNpH5jCHv5YUaUisMxpTBRxqxcPZReO9tJIb1wZjXcwVJrdjmUWaLUpEhtJ/2a8lva6KatdTas9LVPNAWekONhp9i4T7y5dj6W4H+dgHh+iS6BMB6cDDOlvdya3GMWc1x0YPjJiQWwKLQZEJ7Lq1ftuqzPgdCTyHN9T6yG0224Ix+rUSAmK9YICRJvpfwfHNy5evr5yIA2diROqphuOg/u4GRNezHgHHIVhajnM2+dHNoHsDsI7r9+JBFCUZJryz6jIr6iHbRcuWQntBPjxEuD26rtCTDQEE435kE5R0iFYyukod54l+J8v6eXsCHr3y0bxRY9txfrua3nqbHhnhHzky4YwK5+iVQSkgJhRNWh3agkPQIDfVIRoXRx7K3S2jr542e/70qYLDs+NtftDnweMQHEfozRYzcvx9+nQXi0mEAN7WWgxJmVOmyOM3j1BYTPV+bI3LBUPvKGBk7Lj/VCficax79RnwUCUBjut7/K0OAkKQoO5Rg6ExKTK2lU2Gdzq3z5/Dn9W7vvkGVoK/W2JFB/J8D2m7PEDjYQ4y+DfGQ9/RNesnAHIoTDSjJguqi7CCxaqqlPXW/b7Lo6IO72M0HqNqoU2jsXCMRqrlTQBOx+MUn/kTAdGOllJZ3bdoL8c+TCjlzXKdoPfwUNU6bb4tsAAaz8luoBKYQ3Eu57GPjONvbTSsuKuFRyewVuHRc5D9oS/fDcmhu5tUPD9I10GddBwoYk2MLeHbGgx64j5CjMEAGhT+ecDFKBUFaTve2fhj0aBS/MN4RJ8ZDzlXa61j8bB+Og4Rqh7SdRGVxXTHPjfwgLf09OmInNwxZ0ac4T+m5xSw084eOI4AwTrUKPNjUezGw55Ec9RVdE5L9nTh0X76cZBQ9VDOFt7OQX1jhRQWHlqViQyMlWzY/jBX95C95yDE64enCoY6OgyN+ThCPvTJLSw7RkCxmIKzbc+sbJ7VfzXpAkdrLmS6jBkHHu1wSCmbmPCXV69R3vbSdbRULehLjJD78b6uZzmahp8ND49vhzjY2GVXZLeEk4d62QmIECRaKTlWgHo4dXaYbMu95VlnhAbHKbaLSxW7Rw7qHOKnhUeklcZJeNh3bfOC2l2mZsiu43V6su779bXmIBT6CN9KaL+bdY8kZxUa45dXV2w4JGjkg8WMAw9x2YUbp0LSxBFJT43HEVfowaPXo3AK3b2r6fr4LjwOSX9vMsXd9G23cro5pMOkgG9sOKRMHWiIZAh2lpfscOMkQIbteOi52MeS1YI2TdWBh6i2NubiIZUV+Tg6Vme1xeHMYLYb2saTAIin9TxuTY/IOIeOkRpDBz0c5P+IuNtYHZZF0FNXMS3h1so9l9lHAuIZA/9HM4OEHvwwAN69Pg4P4TLzHX+1jbcjRYJD8PjmG55aQNNr7MDpNDzMIXaZLe8jLBrZErejqvpr+95tbDkKjvYDHEC65cS/iFJLRyLiWfJmQNiEQ7vkBB1N8rCEoxOPUz1dxROypk08aDwN73djMIafjod/fLeEWHqrSwpa5t0chUcH3xu7nfEnawxQebkyocMZeLPZ1Pb8fd3UEhHVK61Bb4IjjJJ5+c9zXtPHqDdzxEFEeoSkHSntwrTUzrVx15s9eBIeXckrbU2s6k+FBiCijK8nHIfx6GRJM4hW4ui5QIDjZnMzn5fzKHDrDKww1PcofCNvbtuGXrO9dnWp9HtdZ623XTE5iFobHg4aXm2hG59bPxEc8LgYDp+vLh4daDQfWj+X7FXa0ZIP+jGZ04twftzOLRvOpV3NefEaDxev9hZ5/HM2RUaEBXoejzc/ukVSPgEPzfFvvqEECKeuGpqN6hVktlNbP3f40v3s7i5pl3V4Dx6z2d/+dnfXgsdBPrfdvodN1rwqa7UiA0jj/K4JOEfhEZtxD4fn4/FY4JB6qqZ2e8mBYWsmoQWPlojAZZtqlwdHAw/Yj9ls9qe//sff/mWedOPhXrvZ43tncFqMdCfmGDWP6hz7F+tTnduPUgMPZrgUrnH+lsY4eIDjiuM/d7xcVBhNaebkodFHDVar3e2d1TnHtFufF7C7O2rDA4D89eZ//vhjYjK6jIijJvUctD5uHFFHpXo4yYgFiIWImfLVeZcDosgZ2edPX3q5RMICmRGuAG2TDVVU4gpHEwqtYYbH4uFgyxkDO5vIJxIeb99OZsBD8naoYJJLyhdlak+tWj6AhyMhKGA7hIdt4/vaIng8H3uKSiWqaOCjXVOJx2Wz/4ggqwMT9TT8QPa5Oghz8aC3rMxv/npzsy3prdWs5PzHlUTFgYkwx5I99cMOFQxaysFtnnnczXnakmc2ZB0kKY52an6M0dduldXNR5+Ih1G6jnyIurKFifRVMpvPbn4sE4WH5hltQo/o/cdnkPgiPXjoTxWPOIh0ML8NozZqGHGslnTFaGCg77lTVwVrY6TDhYN41xFHHUDD2nInmEE72H3QTJ3ilw4l83A+n+q91tSqAasR+nI5OI0n3aTxYI/LrjcXpdV9ph2hdN/BtRqObIxkcrKFVSyxCK2U5AuHtXGsZPgoOLGg28Jm3TcBQq/jslDC3ygOB/Hz+BKLUMcxkGFs7LjtI8nKf4huNdxprUx3HtKxM+0NcdGIqS6a1tQjZeQIB6ZgaOnQQ+QNj1Xt6+R9Y+uo+SfNH8JQJqzSP8EEU8Kq6urqD3/4wx++++n29v++Qjb6qlotYlmbKfiMxNZdONU6VcDvXS3y4Ww6cDAaJBxSPkW30raDI0PjV7m5bQ+PLkCOt219eCiRiIIQeGCTJ4HfVtVDFT95Mnjy1eC7avX8q6+ePDkbXN3eYvIYJvG1zhb9OFIPggngBMjAWzLAj8tbH9xhRwMNr0zdkhDjV1mGw4OjJQ7vbAf9cNRkOW0MmqT6exQEOeayVsVi9d3lk8GTJ0+eXH63uBp8BTq7+G6xqnb7D/vHIgrC42TEmud7dJ6Dm+lJhNlleuSB6yhNJS6ui4caTvcth/C8x3oHn0xYfUAbgBbS+ifKsXQIXp+6+E5sRpwVGT6/Ojs7w8tx8P7Qelcn2gvup/Z5150Ntex6R9BnmNItL5Yd5xn8HTNn2Y5joIPdX18pHZED+qJ4hFlRZGlerNdVXa0Wi+++4zcWX4HiOF3Qiwzx+oLHCobkc7fTnmeJrVYtZSkMte1fxSgrjM5y9ryJhhUDtr696ItAcRIeWD46xcvn6S0FeK0mvzl0wUSb/Jr0qi6yXgEJP9LE8Mob2tZZ1rJrFKQTD+Ux8dB4Nx4SG34eAI66As+17sFDLamIefYZ5GO9xpsjvNdwy5vo8QrusijKLDgRj+GpE8P1aRYqrsy0P73itppC06arNBiY0y+caTNYR7XZPiP4fHjQEsV4kT29frXkd05boPBHWaJ6uaiKwM+d9IvE8c+meGYa7ItE215D1pBHh+VwhkU67nJ0o0+WKYVH5wGERxhiqmqSFbAftARVCbXV8qL5LC93VVEcbMhHe8WWjLTlMR1T0sK09hHaA3B8vLr6YnjAi4UFd9aZBC4+KnlW19VOWZ2oC4NPiFIs5pmdriHvHlUXTvetRkKqCla+Pf6UT+ejeVjjy5HgEBp9eGRBcEauaZhkPIFVEy2RCzkBKMAF0OT5dFc9Zv1c/6Qofoj+w0bYW7GF4zXOEnT06F7Z8GbXtt68f7NvHOAYYuk4IB9nsMEkH0WpVtSRNSp43iTZFCADOIqsrneCRzfbeTb4R9lFewE9Xl/K/OAa95Yzj1NVjuk4gXrynZ8Fj/Pzsyg4Ax4h5ncXJa1MociamLemt96vsShCka93Go9OtdSxCteh9uvdZhE9CTVkv1pjo4sznaLhomG8qt5WWg3rHRs9+jqdeJwpIjyQAYG3W653u91+b2GiUBE5KfN5kRU7hIQQjpMjDSe/299yQoQgsRuv81re9RQdhIMGqxQ/TsAj+Hx4NOz5uUbj7CyIgAdemq3wcEmEhN/DWa2LeZ7lgschGWi2W9uVvvygbvuAluD0EXEv6e/4Yqqqh45HVbwrBw8LC8Ijhr6CBSF1ZesrDxb6WyI6rCtaaN1abPlgk7ndDTtvP0gLuiY33nJ8Kx2DxoGhr5PpFDj87K6HBuERKDzIgYLVxvo5bDF41ipjst/t6jVez1XWCg+w8AgpsWoxug9qu45mqTMA0nOnY01He0uskhA/XP8seMSxi0cDDcYDAyCIzrN2fwl552mW0/p5wGNa7IAHfORj8eDU6UmROh/JDLWWDj4Aqqhna1X80ejpP/5jj6o6qkWtx5wiYXSsbhYBcn52dm5bDmU/2GvFwGArYKTOLi7Oggt651BRFNPpTnmzjKR2bltGRngSBMmIvDLSys228NYkYvAF1zMLV6jhkZ6lLNvx+FKW40QyeCjZaMEj1ktEZ61onJ1dBBcXwcXZWcYCUkz/WJG/G0NCWH66RYRWe6Rh2WETj850iEsGj0P8lOF4Bw8e6bDdqr8TOdnSJhI+HguRDv/ICxDwDMik58UUCUUSDBrr1eF4u+Li0gNZ7pSruJzMB33vVxqmvw905rcNTac8os2tOsWIt6ZEdHuPv471GMo9GbTrIcYDRiOkVwV2ikcARM7OzkRhYZ433QCaij81Ek2F5cZzxPr2p+l7SLu/s3/UgWIHGpIfOcjHViNvtfCTnDLdqbpkw+AB7yrW0tAUD95JCqvMAYjgwEDoQKRVQsQOWIF1Fx492oujQ7xLwIyutUyosvEgHP5Pjcbn8G8/MV8C58qCo92/wmJ3QRjlBTQS8b8hHrAfZxdnZ9Fu/7Crsjwravi7rKfsBcptPPRXrPLPVdqq4d3VO2561X1IXRxi6sF8UbOmMrjC8XGG44R6s2PHotB2OFZkGFrcq7MgxaFRWuQMRyceOLb6sK+rPM8KJLCU9eDscH9TaaKEseLDzufty3Pbukgyv43RqnZV1QtHqxZSje3H4yT9Jw3/+vz87Fy8qzZ/NwUvkwzeVcCItOFxcQYBKfb7PUL0rCoJDOUrd+DBcClnV+JC8bn81vrl2m3xmNTOiQdlvzxJM1XB8X/YAWALHN5wygnUrVQPXIyl4+uvu60HuA+vFSsLrwgM2gPf1sWDATk7ix53O7wqJa+qiyAih1dIGRD6q817aHSU9wCdT+HioDako1ovpBsMkItvXERJxz8eEI7Ply05mqgG82uIh6EGNkGcxQgGi0IJh6euzs7OcTHeHe4+7ClEL2iEUOSioa4IDy4FlsSV/skfZZUosUHdhlMhAm2sLmmu52krgeMLFe8c2WTVNFRgnrs6ysns4k8MPMJsUZG6aoLB4TnwwE9BtUfVaFGwARHT0Z5YpF2+uW033hoRk//t4CCD6bi+7kVtOFQkfCR96RF0MuUgYxQcbAJ0/WwQx5dx9t0iBhiepzsYPHny1fl5cH5xcXbxBKcsHh8edqvFgoZAZABEm/NDeaxmTU3jiM4BR2tgkJ7NUlvOcV80sf7JsDAcxiAYPBijII7Pvho8GVwO4gH+Z/rqq7MzVO0+GQyecPkubeIzXiwW38VpXlS7DFGkl09sxB8NE+3meRve1MHHUuODrqtlqJlZ/y+DB7D4muDQ2SujvNh/DeLBE4XCpfoyUDA06QylvGdnT7LVYleQf+WKRTOf6Ogn+iNF5GrDP152dL0fTXnNdmLE5roXkJ9MX1BnAQ62H+IdkbRoATlHbjf+6qsBZhQwCPzJiHRBQhQvimo9ZTwa5YihPepkA+QECuav7GGElCmxRyIkKalLjXk0xY5GzNEajhYvt80faxxz0m7n1+5jwGr6hO4nBDQelpUmPM4AAqZCxc//8IfnfTgAL/72BHgUyPFydjc8stpHe1ZDshPOhGCZGuR6XzhOzy+QvfQ2A8+IWBLiFSwcZO4XLJ1WNzpXosDGg/5ZtoNBIQ0WoJhhEGd48R9ytyjlyReLcTympG8cX8JUx2Ea53G6WOGFvxmqq+OoKIrVAo6yiTbYv3XfKXiYI8q3Ej8YuNjHefYH2xLo8y7t+pLzOxzq+qtPtByfASE9OM18V3gIJpaLZeks+LFBnBUlF/oU2Q7D5FX1Z73sM2YYlFVRohioKNZFiR/GUVUUK1VUbcvHUVN1dK2hesWjysNT3MfbKvzzCiD8wLphRg5Lx2+Di/QkYyXYsVIeVhMPKoOj2sQ0K8o1lSuUU125oOvhUDNalVVCcMiIehSti2KRXbZgYOb3qEwK/25PllJpeo0HrQGh30JP++zZ+CQUWo6012vHIrTgwWAEPEajr78O/kuQzXGBg/GwREJ/J/sBpUQzn/ACxt1+nQCH/X6/q1Sdz5re5VCupyVNQ+ACh2wKPBaUifTyiSZTwvqL/iDz6OGhVoRg/W3wUN/0+o10qLVYAlt2/R5Osez2HI+ThKPLeny6wlJqipku+0Rjmbjc0V1nmGZA8wjqHWBYJ/V+t9/k9Yf9bvd+v8c7m8qy3tfVOiqr9bpekzajGQfFVabfv4pXoThtwZi6/EDk2nzhtHRyQUTMAvHbtucChFq+Q437WonEZub3aGo35t1DNMcTYm220wwI7VQGnfMk5+fnF2e6roGVVgzhKIpyt4dU5Emx2+9nF0m9Vi8NqJNnyW6/K6JiDUDwZlmqgV8goO98dHF5e4bV1QIp8l5h+apEQzFG1BUj5xTT6ajSc7VOZFszQ/DZ8LBAETy0RQceEqcLHiJP0FaYegPzUe/KJErK/T6fTCYTWiggiqIkfJbs99WLYPqmWq+3a5KP3a5aLAZtePhqq5PMgjWm82vrodfOITwIMV5oyGac6warIgb/Ph1psO6k+acRXYeFgERAtJF2dzH0wdaEEFJ4wI6zfMB/gn0o1mVVRFlW7ddZPnk2m0yYVeEkzauyiIKooJdgAw4IDmZCDwaUi/8oYnGQdbrkhaN6URt7vrEYFLE4xr3y8KDBhcPyoXq+9Wn4+Om4GKdK22sxJMrdtSIRiRIBDPIlIh+Y8wTiz7wssigIJ7+/Tvlt0JMwDLMiQ3UWv70UE3AByODsq68GqG1sEwU7RKcyFL/dsjatse5qyVl77S6x4MoHIxDF1NMGrAmfwlc9SV999IDUwTNI/3g5cktClJxAcuhoccTo3JiwUHBEcZpk4ygIJtc/5+NvvhnFtOxMyq+FX9FLS2XCziL+GnjIAHpjWMo2721FDrwAG/PzEEmMYnlZEheKI6yTLLZxPsznj43KD53G5sADw8KD7YgJABVhJudZgBVlplPGhNbETYfDOJosH+rXv/vdOE3TfwrTFKvlsnggNqn3+7paLGheOrWAWHLq7ChrcYrW1WH9bWXcleVX9oRSNlxvZ5vhI5jdSKd9HmL1pKGQPzYeJho0eAQ08eOs0T/TOB6N48kP7yvC45/SMEzjCCv9oMiaIXm/r1f51f/100+LTAvAiTNBJH/FgDg6qgMPWTlQiRXHi9YFrRjx7wGCRa6ekgidQhD+1BHHOY2Fa+zIirBC4lekE4VhNg6CSZqm3/y3/zYMJ2EQpHEYp1nG09DLslwuN5syPx88v6oKD4VWyfD0lY7biSdcU9e1iqy1S4WBKk5Ra/F8NB7tA/WfSC0FuWzTCQ0nOOcMIn4RfRVgtDZ89uyZDUgQZPF5GIYXwT/8wz+cX0xopYAgihKxM3l+PZnMlqvV2dlXA5EPi9rwaANJs9Ht/008tANmFgZm86PWfiFP6zMsrhB8OrXWUylEDB4sG+xW0Rc+Jg5Qu/sMFIaY6wRHKAxQrxg9exbEw/8+jp5NwuEYs/+x1HsynU6nSTJ59mwyWy4GX53Fi2nnBNvDref0iGUgmmCYVIle75YR4CSktezLCUs7dsz8CD6d7JFxn0w0KBYeJwhWWj6C+OLZs2cXJCFEwcVFlEdheBFmr169epUBpOKxirI0wjpyMP7hs2e/n0ySVTY4ixcyQKi4b6PDwmYcLiOAyl9SYblt1LsX9lRny0FKRXH0fsILQr4QcXK2OaND2A8zQbKhDzJZXvkbBedDkY9nz0RthcEF3CzkB7M3b7JplERZ8bDL0lU+CRG2T+jo308mZR5cLBZixRvMsNJXKs+r1Q/v08qI+7jsblgNb4dei1anWHhAhOTj749JLynvylFi1jm8UCLLx7MQFdNkNvDSalBW7dbFdFqU1a7OsiIJcdjvJ79n+CZFEcSLRScHDG8k6KYaehXXcbrRlQTWV0pr9b5GxyqLUIIGsvWQ5FMbZA1l/R3gEKOhBgbdk2hOVBQ+u7iAZPAcDxTqKj4WRZaAcQnEJKEDnj0TAQmTosyurr7rthOu6pJ9SkA4ZMcfE6Gr9G0Tj+ZS6nqKFLldairIsXz+O+Gh8oa6rJ1siHVEEERjsuPKdCjugbC2TJ7R+1qmUZJnEQMymUCink3ybL14PRqcqdWajnOwlAExf/RuvVq5thLd2kscAeVnMSzB35ucYaZOdUWMlz3+IfzUGhBiTRBNpxEcqWlOf6cvXmTTCEoMwoMVYsMQOcbiTXU1+PpseCQeCgf5lL1c12P5vLT8fwOPppDopDzLG78U1r7l3wEexHoH0OgFDPLBaNC7cqRzBkGC3O+FVI8Cdjz9VHCLoiRN0yzP37yp4u7xD4t4VoI4W+abtvY6E6LSUe2+r/i2apNw5BvoDIpTJNTRmi+IUx+rZZiw5Rg7dSK9VcSE/iVROA25cJT/Pzs7wyDdK8MZCtWL4s33R+LB/7NckNXQEqKDAcVkwcd5zYad7jVyQykrVVSnZiQ2Fkn7jKTAPzWva/PdwkzXnOhd5F6ph+ZuTGISYDV3iAy2tAXOLL5wOvjP/14NrhrmQ5NmuhrLFd83wkJCVv7RStLqugXcRJqmh0gEDxXFE+vpWHO7z4LHpzhgNsO7xKBfW7l+ZRIFOUGArxgdpBHCKIrOpvZREI9yvfv3v1zd0lw3Tc1gXfd7ncQioP0kigq6oyAY63EQzo1QYn44jL1RET1aSHpM1XF9HvH46KtAPHrcrF7joQBx8QizKb8Cb0qw8IhtFEUFmXYIxitaUYPqfm4Xj+mhAULPvEM0eKzKKjfR8sGekpZYgwfPd1MKzNRnSTpSBg4/lo2mHSftb6UePA5Y8xY8oigEGLx8n8zUTMiqrNUQSfYKgBRF8eZNVV391K2vbFIyIpkVN46WAgKJtjmNS/sZD1tRWfKh5r1J3Y9f13g8DT//4GA3Hr3ycR7Y6oqNRRBhZQysx4AFGShGxHZUIH0V6ZFE0LpaXKbHLVTtrd+g1j7RG/ykZhxESnyJx0rjqYIgx7rD2svJfWto9PH2c+PRhQX97cUD4UdsjS9EPK7E85dJybNTip3IuJO5ice8pnjxz2/eLGJKt/PAr0cNU0KYu4dI/OE+reQbRVnJYLkEJCqRqwyIKDaRnZYkby/32gqvWo7qTL10ULsqOmzPz86CYWS9J5NSdEFQZChrmFLpdFFMs2mSZVP3/bb4afrHN98vrq6Ob6YqHrF20avAbcZIflAGApX6Yv9X1VurXJV+B5Cqr+ueithBn3l4kNK1HQrrgKbSqNnr93PnpCIta/CVSj05/JKHGEZjmJE/vvn+tQyfH0WedlJ7JQmlChN5WIOPJA5LAal6TTJH4rona61lSoc+nqEtseS5mtlxBHSUue2Qj6Pg4PyihQdEhM6MilRBFuURXc6sdjuMXjAeWRxjSKub/CF1OxBsTBlpnKzzIMwRU5xlc0i9L1zGD7uMuo7k+1jLoLJ2aj+oT3MpRhzJ+7MOOLiZhmhMNw2ySPAoMiyjcWYfE0Xj8fjFiz+O44EvH0eUxxmGtbNOv1pM6TcBUVeWKv0kKSwxJGrFgej/A4Xz1eg=";
        private var lessonPreview:Bitmap;
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
            lessonPreview = new Bitmap();
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
                var alphabet:String = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
                var bytes:ByteArray = new ByteArray();
                var value:uint = 0;
                var bits:int = 0;
                for (var i:int = 0; i < POWER_SHOTS_PIXELS.length; ++i)
                {
                    var character:String = POWER_SHOTS_PIXELS.charAt(i);
                    if (character == "=") break;
                    var digit:int = alphabet.indexOf(character);
                    if (digit < 0) throw new Error("Invalid embedded image");
                    value = (value << 6) | digit; bits += 6;
                    if (bits >= 8)
                    {
                        bits -= 8; bytes.writeByte((value >> bits) & 255);
                        value &= (1 << bits) - 1;
                    }
                }
                if (bytes.length != 20648) throw new Error("Invalid image length");
                bytes.position = 0; bytes.uncompress();
                if (bytes.length != 90000) throw new Error("Invalid image dimensions");
                bytes.position = 0;
                var pixels:ByteArray = new ByteArray();
                for (var pixel:int = 0; pixel < 90000; ++pixel)
                {
                    var index:uint = bytes.readUnsignedByte();
                    var red:uint = (index >> 5) & 7;
                    var green:uint = (index >> 2) & 7;
                    pixels.writeByte(255);
                    pixels.writeByte((red << 5) | (red << 2) | (red >> 1));
                    pixels.writeByte((green << 5) | (green << 2) | (green >> 1));
                    pixels.writeByte((index & 3) * 85);
                }
                pixels.position = 0;
                var bitmap:BitmapData = new BitmapData(400, 225, false, 0);
                bitmap.setPixels(new Rectangle(0, 0, 400, 225), pixels);
                lessonPreview.bitmapData = bitmap;
                lessonPreview.smoothing = true;
                lessonPreviewState = 2;
            }
            catch (error:Error) { lessonPreviewState = 3; lessonPreview.visible = false; }
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
            if (String(browser.tab) == "lessons") loadLessonPreview();
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
                            var thumbnail:Bitmap = new Bitmap(lessonPreview.bitmapData);
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

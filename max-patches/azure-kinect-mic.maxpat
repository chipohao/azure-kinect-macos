{
	"patcher" : 	{
		"fileversion" : 1,
		"appversion" : 		{
			"major" : 9,
			"minor" : 0,
			"revision" : 0,
			"architecture" : "x64",
			"modernui" : 1
		},
		"classnamespace" : "box",
		"rect" : [ 100.0, 100.0, 1000.0, 750.0 ],
		"gridsize" : [ 15.0, 15.0 ],
		"boxes" : [ 			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Azure Kinect DK — 7-Channel Microphone Array (macOS)\n\n1. 在 Max Audio Status 中選擇 Azure Kinect Microphone Array 作為輸入裝置\n2. 設定 Sample Rate 為 48000 Hz\n3. 開啟 DSP（點擊 [ezdac~] 或按 cmd+/）\n4. 7 個 meter~ 分別顯示各聲道音量",
					"linecount" : 6,
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 30.0, 450.0, 100.0 ],
					"id" : "obj-1",
					"fontsize" : 12.0,
					"textcolor" : [ 0.2, 0.2, 0.2, 1.0 ]
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 1",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label1",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 2",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 120.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label2",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 3",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 210.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label3",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 4",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 300.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label4",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 5",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 390.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label5",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 6",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 480.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label6",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Ch 7",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 570.0, 150.0, 40.0, 20.0 ],
					"id" : "obj-label7",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "adc~ 1 2 3 4 5 6 7",
					"numinlets" : 1,
					"numoutlets" : 7,
					"outlettype" : [ "signal", "signal", "signal", "signal", "signal", "signal", "signal" ],
					"patching_rect" : [ 30.0, 180.0, 560.0, 22.0 ],
					"id" : "obj-2"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 30.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m1"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 120.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m2"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 210.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m3"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 300.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m4"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 390.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m5"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 480.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m6"
				}
			},
			{
				"box" : 				{
					"maxclass" : "meter~",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "float" ],
					"patching_rect" : [ 570.0, 220.0, 60.0, 180.0 ],
					"id" : "obj-m7"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "gain~ 150",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "signal", "" ],
					"patching_rect" : [ 30.0, 440.0, 63.0, 22.0 ],
					"id" : "obj-gain1"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "gain~ 150",
					"numinlets" : 2,
					"numoutlets" : 2,
					"outlettype" : [ "signal", "" ],
					"patching_rect" : [ 120.0, 440.0, 63.0, 22.0 ],
					"id" : "obj-gain2"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "dac~ 1 2",
					"numinlets" : 2,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 490.0, 109.0, 22.0 ],
					"id" : "obj-dac"
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "監聽 Ch 1-2 (透過 gain~ 控制音量)",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 420.0, 250.0, 20.0 ],
					"id" : "obj-comment-monitor",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "ezdac~",
					"numinlets" : 2,
					"numoutlets" : 0,
					"patching_rect" : [ 700.0, 300.0, 45.0, 45.0 ],
					"id" : "obj-ezdac"
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "DSP On/Off",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 700.0, 280.0, 70.0, 20.0 ],
					"id" : "obj-dsp-label",
					"fontsize" : 11.0
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "麥克風陣列配置 (環形)\n\n     Ch2\n  Ch3   Ch1\nCh4       Ch7\n  Ch5   Ch6\n     (中心)\n\n7 個 MEMS 麥克風\n環形排列，適合空間音訊\n和波束成形應用",
					"linecount" : 11,
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 670.0, 400.0, 180.0, 170.0 ],
					"id" : "obj-mic-layout",
					"fontsize" : 11.0,
					"textcolor" : [ 0.4, 0.4, 0.4, 1.0 ]
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "設定：Max > Audio Status > Input Device > Azure Kinect Microphone Array\nSample Rate: 48000 Hz",
					"linecount" : 2,
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 550.0, 500.0, 35.0 ],
					"id" : "obj-settings",
					"fontsize" : 11.0,
					"textcolor" : [ 0.6, 0.2, 0.2, 1.0 ]
				}
			}
		],
		"lines" : [ 			{
				"patchline" : 				{
					"source" : [ "obj-2", 0 ],
					"destination" : [ "obj-m1", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 1 ],
					"destination" : [ "obj-m2", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 2 ],
					"destination" : [ "obj-m3", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 3 ],
					"destination" : [ "obj-m4", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 4 ],
					"destination" : [ "obj-m5", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 5 ],
					"destination" : [ "obj-m6", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 6 ],
					"destination" : [ "obj-m7", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 0 ],
					"destination" : [ "obj-gain1", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-2", 1 ],
					"destination" : [ "obj-gain2", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-gain1", 0 ],
					"destination" : [ "obj-dac", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-gain2", 0 ],
					"destination" : [ "obj-dac", 1 ]
				}
			}
		]
	}
}

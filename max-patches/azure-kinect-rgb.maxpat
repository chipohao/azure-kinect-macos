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
		"rect" : [ 100.0, 100.0, 900.0, 700.0 ],
		"gridsize" : [ 15.0, 15.0 ],
		"boxes" : [ 			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "Azure Kinect DK — RGB Camera (macOS)\n\n1. 點擊 [open] 開啟攝影機\n2. 使用 umenu 選擇 Azure Kinect 4K Camera\n3. 點擊 [toggle] 開始擷取\n4. 透過 number box 調整解析度",
					"linecount" : 6,
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 30.0, 350.0, 100.0 ],
					"id" : "obj-1",
					"fontsize" : 12.0,
					"textcolor" : [ 0.2, 0.2, 0.2, 1.0 ]
				}
			},
			{
				"box" : 				{
					"maxclass" : "message",
					"text" : "open",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 30.0, 150.0, 40.0, 22.0 ],
					"id" : "obj-2"
				}
			},
			{
				"box" : 				{
					"maxclass" : "message",
					"text" : "close",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 80.0, 150.0, 43.0, 22.0 ],
					"id" : "obj-3"
				}
			},
			{
				"box" : 				{
					"maxclass" : "umenu",
					"numinlets" : 1,
					"numoutlets" : 3,
					"outlettype" : [ "int", "", "" ],
					"patching_rect" : [ 150.0, 150.0, 200.0, 22.0 ],
					"id" : "obj-4"
				}
			},
			{
				"box" : 				{
					"maxclass" : "message",
					"text" : "getdevlist",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 150.0, 120.0, 68.0, 22.0 ],
					"id" : "obj-5"
				}
			},
			{
				"box" : 				{
					"maxclass" : "toggle",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "int" ],
					"patching_rect" : [ 30.0, 200.0, 24.0, 24.0 ],
					"id" : "obj-6"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "qmetro 33",
					"numinlets" : 1,
					"numoutlets" : 1,
					"outlettype" : [ "bang" ],
					"patching_rect" : [ 30.0, 240.0, 65.0, 22.0 ],
					"id" : "obj-7"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "t b b",
					"numinlets" : 1,
					"numoutlets" : 2,
					"outlettype" : [ "bang", "bang" ],
					"patching_rect" : [ 30.0, 275.0, 35.0, 22.0 ],
					"id" : "obj-8"
				}
			},
			{
				"box" : 				{
					"maxclass" : "message",
					"text" : "dim 1920 1080",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 400.0, 150.0, 95.0, 22.0 ],
					"id" : "obj-9"
				}
			},
			{
				"box" : 				{
					"maxclass" : "message",
					"text" : "dim 3840 2160",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 510.0, 150.0, 95.0, 22.0 ],
					"id" : "obj-10"
				}
			},
			{
				"box" : 				{
					"maxclass" : "message",
					"text" : "dim 1280 720",
					"numinlets" : 2,
					"numoutlets" : 1,
					"outlettype" : [ "" ],
					"patching_rect" : [ 400.0, 180.0, 88.0, 22.0 ],
					"id" : "obj-11"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "jit.grab @output_texture 1",
					"numinlets" : 1,
					"numoutlets" : 2,
					"outlettype" : [ "jit_matrix", "" ],
					"patching_rect" : [ 30.0, 320.0, 160.0, 22.0 ],
					"id" : "obj-12"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "jit.world azure-kinect @floating 1 @size 960 540",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 30.0, 400.0, 290.0, 22.0 ],
					"id" : "obj-13"
				}
			},
			{
				"box" : 				{
					"maxclass" : "newobj",
					"text" : "jit.gl.videoplane azure-kinect @transform_reset 2 @blend_enable 1",
					"numinlets" : 1,
					"numoutlets" : 2,
					"outlettype" : [ "jit_matrix", "" ],
					"patching_rect" : [ 30.0, 360.0, 380.0, 22.0 ],
					"id" : "obj-14"
				}
			},
			{
				"box" : 				{
					"maxclass" : "comment",
					"text" : "解析度選擇",
					"numinlets" : 1,
					"numoutlets" : 0,
					"patching_rect" : [ 400.0, 120.0, 80.0, 20.0 ],
					"id" : "obj-15",
					"fontsize" : 11.0
				}
			}
		],
		"lines" : [ 			{
				"patchline" : 				{
					"source" : [ "obj-2", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-3", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-4", 1 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-5", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-6", 0 ],
					"destination" : [ "obj-7", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-7", 0 ],
					"destination" : [ "obj-8", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-8", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-8", 1 ],
					"destination" : [ "obj-13", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-9", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-10", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-11", 0 ],
					"destination" : [ "obj-12", 0 ]
				}
			},
			{
				"patchline" : 				{
					"source" : [ "obj-12", 0 ],
					"destination" : [ "obj-14", 0 ]
				}
			}
		]
	}
}

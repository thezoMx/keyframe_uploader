--[[
	KeyframeUploader plugin
	------------------------
	Select one or more KeyframeSequences in the Explorer, set a destination path, and
	click Upload. The plugin serializes the selected animations and POSTs them to the
	local companion server (server.py), which uploads them to Roblox via Open Cloud and
	returns the asset ids. The plugin then creates Animation instances (named after each
	KeyframeSequence) at the configured destination, creating any missing folders.

	Install: right-click this Script in Explorer -> "Save as Local Plugin".
	The companion server must be running (default http://127.0.0.1:34567).

	Single-file on purpose so it is trivial to install and distribute.
]]

local Selection = game:GetService("Selection")
local HttpService = game:GetService("HttpService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local SETTING_PREFIX = "KeyframeUploader_"
local DEFAULT_SERVER_URL = "http://127.0.0.1:34567"
local FALLBACK_ROOT = "ReplicatedStorage"
local FALLBACK_PATH = "UPLOADED_ANIMATIONS"

----------------------------------------------------------------------
-- Settings persistence
----------------------------------------------------------------------

local function getSetting(key, default)
	local value = plugin:GetSetting(SETTING_PREFIX .. key)
	if value == nil then
		return default
	end
	return value
end

local function setSetting(key, value)
	plugin:SetSetting(SETTING_PREFIX .. key, value)
end

----------------------------------------------------------------------
-- Serialization
----------------------------------------------------------------------

local function serializePose(pose)
	local children = {}
	for _, child in ipairs(pose:GetChildren()) do
		if child:IsA("Pose") then
			table.insert(children, serializePose(child))
		end
	end
	return {
		name = pose.Name,
		weight = pose.Weight,
		easingStyle = pose.EasingStyle.Value,
		easingDirection = pose.EasingDirection.Value,
		cframe = { pose.CFrame:GetComponents() },
		poses = children,
	}
end

local function serializeKeyframe(keyframe)
	local poses = {}
	for _, child in ipairs(keyframe:GetChildren()) do
		if child:IsA("Pose") then
			table.insert(poses, serializePose(child))
		end
	end
	return {
		time = keyframe.Time,
		name = keyframe.Name,
		poses = poses,
	}
end

local function serializeKeyframeSequence(kfs)
	local keyframes = {}
	for _, child in ipairs(kfs:GetChildren()) do
		if child:IsA("Keyframe") then
			table.insert(keyframes, serializeKeyframe(child))
		end
	end
	table.sort(keyframes, function(a, b)
		return a.time < b.time
	end)
	return {
		name = kfs.Name,
		loop = kfs.Loop,
		priority = kfs.Priority.Value,
		authoredHipHeight = kfs.AuthoredHipHeight,
		keyframes = keyframes,
	}
end

local function collectSelectedSequences()
	local sequences = {}
	for _, instance in ipairs(Selection:Get()) do
		if instance:IsA("KeyframeSequence") then
			table.insert(sequences, serializeKeyframeSequence(instance))
		end
	end
	return sequences
end

----------------------------------------------------------------------
-- Destination structure
----------------------------------------------------------------------

local function trim(s)
	return (string.gsub(s, "^%s*(.-)%s*$", "%1"))
end

local function resolveRoot(rootStr)
	rootStr = trim(rootStr or "")
	if rootStr == "" then
		return ReplicatedStorage
	end
	local ok, service = pcall(function()
		return game:GetService(rootStr)
	end)
	if ok and service then
		return service
	end
	-- Fall back to a child of game (e.g. a top-level folder name) or ReplicatedStorage.
	local child = game:FindFirstChild(rootStr)
	return child or ReplicatedStorage
end

local function ensureFolderPath(root, pathStr)
	local parent = root
	for _, rawSegment in ipairs(string.split(pathStr or "", "/")) do
		local segment = trim(rawSegment)
		if segment ~= "" then
			local existing = parent:FindFirstChild(segment)
			if not (existing and existing:IsA("Folder")) then
				existing = Instance.new("Folder")
				existing.Name = segment
				existing.Parent = parent
			end
			parent = existing
		end
	end
	return parent
end

local function placeAnimation(targetFolder, name, assetId)
	local anim = targetFolder:FindFirstChild(name)
	if not (anim and anim:IsA("Animation")) then
		anim = Instance.new("Animation")
		anim.Name = name
		anim.Parent = targetFolder
	end
	anim.AnimationId = "rbxassetid://" .. tostring(assetId)
	return anim
end

-- Builds Animation instances for the uploaded results. Returns count created.
local function buildStructure(results, rootStr, pathStr)
	local trimmedPath = trim(pathStr or "")
	local root, finalPath
	if trimmedPath == "" then
		root = resolveRoot(FALLBACK_ROOT)
		finalPath = FALLBACK_PATH
	else
		root = resolveRoot(rootStr)
		finalPath = trimmedPath
	end

	local recording = ChangeHistoryService:TryBeginRecording("KeyframeUploader: build animations")
	local placed = 0
	for _, result in ipairs(results) do
		if result.assetId then
			local folder = ensureFolderPath(root, finalPath)
			placeAnimation(folder, result.name, result.assetId)
			placed += 1
		end
	end
	if recording then
		ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
	else
		ChangeHistoryService:SetWaypoint("KeyframeUploader: build animations")
	end
	return placed, root, finalPath
end

----------------------------------------------------------------------
-- Networking
----------------------------------------------------------------------

local function uploadSequences(serverUrl, sequences)
	local body = HttpService:JSONEncode({ animations = sequences })
	local ok, response = pcall(function()
		return HttpService:RequestAsync({
			Url = serverUrl .. "/upload",
			Method = "POST",
			Headers = { ["Content-Type"] = "application/json" },
			Body = body,
		})
	end)
	if not ok then
		return nil, "Could not reach the server. Is it running? (" .. tostring(response) .. ")"
	end
	if not response.Success then
		return nil, string.format("Server returned %d: %s", response.StatusCode, response.Body)
	end
	local decoded
	local decodeOk = pcall(function()
		decoded = HttpService:JSONDecode(response.Body)
	end)
	if not decodeOk or not decoded then
		return nil, "Could not parse server response."
	end
	return decoded.results or {}, nil
end

----------------------------------------------------------------------
-- UI
----------------------------------------------------------------------

local toolbar = plugin:CreateToolbar("KeyframeUploader")
local button = toolbar:CreateButton(
	"Uploader",
	"Open the KeyframeUploader panel",
	"rbxasset://textures/AnimationEditor/icon_save.png"
)

local widget = plugin:CreateDockWidgetPluginGui(
	"KeyframeUploaderWidget",
	DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Float, false, false, 320, 360, 280, 300)
)
widget.Title = "KeyframeUploader"

local root = Instance.new("Frame")
root.Size = UDim2.fromScale(1, 1)
root.BackgroundColor3 = Color3.fromRGB(46, 46, 46)
root.BorderSizePixel = 0
root.Parent = widget

local padding = Instance.new("UIPadding")
padding.PaddingTop = UDim.new(0, 8)
padding.PaddingBottom = UDim.new(0, 8)
padding.PaddingLeft = UDim.new(0, 8)
padding.PaddingRight = UDim.new(0, 8)
padding.Parent = root

local layout = Instance.new("UIListLayout")
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Padding = UDim.new(0, 6)
layout.Parent = root

local order = 0
local function nextOrder()
	order += 1
	return order
end

local function makeLabel(text)
	local label = Instance.new("TextLabel")
	label.Size = UDim2.new(1, 0, 0, 16)
	label.BackgroundTransparency = 1
	label.TextColor3 = Color3.fromRGB(200, 200, 200)
	label.TextXAlignment = Enum.TextXAlignment.Left
	label.Font = Enum.Font.Gotham
	label.TextSize = 13
	label.Text = text
	label.LayoutOrder = nextOrder()
	label.Parent = root
	return label
end

local function makeTextBox(default, placeholder, settingKey)
	local box = Instance.new("TextBox")
	box.Size = UDim2.new(1, 0, 0, 26)
	box.BackgroundColor3 = Color3.fromRGB(30, 30, 30)
	box.BorderColor3 = Color3.fromRGB(70, 70, 70)
	box.TextColor3 = Color3.fromRGB(235, 235, 235)
	box.PlaceholderText = placeholder
	box.PlaceholderColor3 = Color3.fromRGB(120, 120, 120)
	box.Font = Enum.Font.Code
	box.TextSize = 14
	box.TextXAlignment = Enum.TextXAlignment.Left
	box.ClearTextOnFocus = false
	box.Text = default
	box.LayoutOrder = nextOrder()
	box.Parent = root
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0, 6)
	pad.PaddingRight = UDim.new(0, 6)
	pad.Parent = box
	box.FocusLost:Connect(function()
		setSetting(settingKey, box.Text)
	end)
	return box
end

makeLabel("Server URL")
local serverBox = makeTextBox(getSetting("serverUrl", DEFAULT_SERVER_URL), DEFAULT_SERVER_URL, "serverUrl")

makeLabel("Root (service or top-level name)")
local rootBox = makeTextBox(getSetting("root", "ReplicatedStorage"), "ReplicatedStorage", "root")

makeLabel("Destination path (e.g. WeaponName/Attacks)")
local pathBox = makeTextBox(getSetting("path", ""), "blank -> ReplicatedStorage/UPLOADED_ANIMATIONS", "path")

local uploadButton = Instance.new("TextButton")
uploadButton.Size = UDim2.new(1, 0, 0, 34)
uploadButton.BackgroundColor3 = Color3.fromRGB(0, 120, 215)
uploadButton.BorderSizePixel = 0
uploadButton.TextColor3 = Color3.fromRGB(255, 255, 255)
uploadButton.Font = Enum.Font.GothamBold
uploadButton.TextSize = 15
uploadButton.Text = "Upload selected animations"
uploadButton.LayoutOrder = nextOrder()
uploadButton.Parent = root

local status = Instance.new("TextLabel")
status.Size = UDim2.new(1, 0, 1, -200)
status.BackgroundColor3 = Color3.fromRGB(24, 24, 24)
status.BorderColor3 = Color3.fromRGB(70, 70, 70)
status.TextColor3 = Color3.fromRGB(210, 210, 210)
status.Font = Enum.Font.Code
status.TextSize = 13
status.TextXAlignment = Enum.TextXAlignment.Left
status.TextYAlignment = Enum.TextYAlignment.Top
status.TextWrapped = true
status.Text = "Select KeyframeSequences and click Upload."
status.LayoutOrder = nextOrder()
status.Parent = root
local statusPad = Instance.new("UIPadding")
statusPad.PaddingTop = UDim.new(0, 4)
statusPad.PaddingLeft = UDim.new(0, 6)
statusPad.PaddingRight = UDim.new(0, 6)
statusPad.Parent = status

local function setStatus(text)
	status.Text = text
	print("[KeyframeUploader] " .. text)
end

----------------------------------------------------------------------
-- Upload flow
----------------------------------------------------------------------

local busy = false

local function doUpload()
	if busy then
		return
	end
	local sequences = collectSelectedSequences()
	if #sequences == 0 then
		setStatus("No KeyframeSequence selected. Select one or more and try again.")
		return
	end

	busy = true
	uploadButton.Text = "Uploading..."
	uploadButton.AutoButtonColor = false
	setStatus(string.format("Uploading %d animation(s)...", #sequences))

	task.defer(function()
		local serverUrl = trim(serverBox.Text)
		if serverUrl == "" then
			serverUrl = DEFAULT_SERVER_URL
		end

		local results, err = uploadSequences(serverUrl, sequences)
		if err then
			setStatus("Error: " .. err)
		else
			local placed, root, finalPath = buildStructure(results, rootBox.Text, pathBox.Text)
			local lines = {
				string.format("Placed %d animation(s) under %s/%s:", placed, root.Name, finalPath),
			}
			for _, result in ipairs(results) do
				if result.assetId then
					table.insert(lines, string.format("  OK  %s = %s", result.name, tostring(result.assetId)))
				else
					table.insert(lines, string.format("  ERR %s : %s", result.name, tostring(result.error)))
				end
			end
			setStatus(table.concat(lines, "\n"))
			Selection:Set({})
		end

		busy = false
		uploadButton.Text = "Upload selected animations"
		uploadButton.AutoButtonColor = true
	end)
end

uploadButton.Activated:Connect(doUpload)

button.Click:Connect(function()
	widget.Enabled = not widget.Enabled
end)

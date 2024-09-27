import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';
import 'dart:convert';

void main() {
  runApp(const DiffReviewerApp());
}

class DiffReviewerApp extends StatelessWidget {
  const DiffReviewerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Diff Reviewer',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<DiffReview> reviews = [];

  @override
  void initState() {
    super.initState();
    loadReviews();
  }

  void loadReviews() async {
    final prefs = await SharedPreferences.getInstance();
    final savedReviews = prefs.getStringList('diffReviews') ?? [];
    final loadedReviews = await compute(parseSavedReviews, savedReviews);
    setState(() {
      reviews = loadedReviews;
    });
  }

  void saveReviews() async {
    final prefs = await SharedPreferences.getInstance();
    final serializedReviews = reviews
        .map((review) => jsonEncode({
              'name': review.name,
              'files': review.files
                  .map((file) => {
                        'name': file.name,
                        'content': file.content,
                        'isReviewed': file.isReviewed,
                        'note': file.note,
                      })
                  .toList(),
            }))
        .toList();
    await prefs.setStringList('diffReviews', serializedReviews);
  }

  Future<void> createNewReview() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['diff'],
    );

    if (result != null) {
      File file = File(result.files.single.path!);
      String content = await file.readAsString();

      final newReview = await compute(parseDiffReview, {
        'name': result.files.single.name,
        'content': content,
      });

      setState(() {
        reviews.add(newReview);
      });

      saveReviews();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Diff Reviews'),
      ),
      body: ListView.builder(
        itemCount: reviews.length,
        itemBuilder: (context, index) {
          final review = reviews[index];
          final progress =
              review.files.where((file) => file.isReviewed).length /
                  review.files.length;
          return ListTile(
            title: Text(review.name),
            subtitle: LinearProgressIndicator(value: progress),
            trailing: Text('${(progress * 100).toStringAsFixed(0)}%'),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (context) => ReviewScreen(review: review)),
              ).then((_) => saveReviews());
            },
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: createNewReview,
        tooltip: 'New Review',
        child: const Icon(Icons.add),
      ),
    );
  }
}

class ReviewScreen extends StatefulWidget {
  final DiffReview review;

  const ReviewScreen({super.key, required this.review});

  @override
  _ReviewScreenState createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  String fileNameFilter = '';
  Set<String> selectedFiles = {};
  bool selectAll = false;
  int? selectedFileIndex;

  List<DiffFile> getFilteredFiles() {
    return widget.review.files
        .where((file) =>
            file.name.toLowerCase().contains(fileNameFilter.toLowerCase()))
        .toList();
  }

  void toggleSelectAll(bool? value) {
    setState(() {
      selectAll = value ?? false;
      if (selectAll) {
        selectedFiles = Set.from(getFilteredFiles().map((file) => file.name));
      } else {
        selectedFiles.clear();
      }
    });
  }

  void applyBulkAction(Function(DiffFile) action) {
    setState(() {
      for (var file in widget.review.files) {
        if (selectedFiles.contains(file.name)) {
          action(file);
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final filteredFiles = getFilteredFiles();

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.review.name),
        actions: [
          IconButton(
            icon: const Icon(Icons.play_arrow),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (context) =>
                        ZenModeScreen(files: widget.review.files)),
              ).then((_) => setState(() {}));
            },
          ),
        ],
      ),
      body: Row(
        children: [
          Expanded(
            flex: 2,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: TextField(
                    decoration: const InputDecoration(
                      labelText: 'File Name Filter',
                      suffixIcon: Icon(Icons.search),
                    ),
                    onChanged: (value) {
                      setState(() {
                        fileNameFilter = value;
                        selectAll = false;
                        selectedFiles.clear();
                      });
                    },
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16.0),
                  child: Row(
                    children: [
                      Checkbox(
                        value: selectAll,
                        onChanged: toggleSelectAll,
                      ),
                      const Text('Select All'),
                      const Spacer(),
                      ElevatedButton(
                        child: const Text('Mark Reviewed'),
                        onPressed: () =>
                            applyBulkAction((file) => file.isReviewed = true),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        child: const Text('Mark Unreviewed'),
                        onPressed: () =>
                            applyBulkAction((file) => file.isReviewed = false),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    itemCount: filteredFiles.length,
                    itemBuilder: (context, index) {
                      final file = filteredFiles[index];
                      return ListTile(
                        title: Text(file.name),
                        subtitle:
                            Text(file.isReviewed ? 'Reviewed' : 'Not reviewed'),
                        leading: Checkbox(
                          value: selectedFiles.contains(file.name),
                          onChanged: (value) {
                            setState(() {
                              if (value!) {
                                selectedFiles.add(file.name);
                              } else {
                                selectedFiles.remove(file.name);
                              }
                              selectAll =
                                  selectedFiles.length == filteredFiles.length;
                            });
                          },
                        ),
                        trailing: Icon(
                          file.status == FileStatus.modified
                              ? Icons.edit
                              : file.status == FileStatus.added
                                  ? Icons.add_circle
                                  : Icons.remove_circle,
                          color: file.status == FileStatus.modified
                              ? Colors.orange
                              : file.status == FileStatus.added
                                  ? Colors.green
                                  : Colors.red,
                        ),
                        onTap: () {
                          setState(() {
                            selectedFileIndex =
                                widget.review.files.indexOf(file);
                          });
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (context) =>
                                    DiffViewerScreen(file: file)),
                          ).then((_) => setState(() {}));
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(
            flex: 1,
            child: NotesPanel(
              file: selectedFileIndex != null
                  ? widget.review.files[selectedFileIndex!]
                  : null,
              onNoteChanged: (String newNote) {
                if (selectedFileIndex != null) {
                  setState(() {
                    widget.review.files[selectedFileIndex!].note = newNote;
                  });
                }
              },
            ),
          ),
        ],
      ),
    );
  }
}

class NotesPanel extends StatelessWidget {
  final DiffFile? file;
  final Function(String) onNoteChanged;

  const NotesPanel({super.key, this.file, required this.onNoteChanged});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const Padding(
          padding: EdgeInsets.all(8.0),
          child: Text('Notes',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        ),
        if (file != null)
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(8.0),
              child: TextField(
                decoration: const InputDecoration(
                  hintText: 'Enter note here',
                  border: OutlineInputBorder(),
                ),
                maxLines: null,
                controller: TextEditingController(text: file!.note ?? ''),
                onChanged: onNoteChanged,
              ),
            ),
          )
        else
          const Expanded(
            child: Center(
              child: Text('Select a file to view or edit notes'),
            ),
          ),
      ],
    );
  }
}

class ZenModeScreen extends StatefulWidget {
  final List<DiffFile> files;

  const ZenModeScreen({super.key, required this.files});

  @override
  _ZenModeScreenState createState() => _ZenModeScreenState();
}

class _ZenModeScreenState extends State<ZenModeScreen> {
  int currentIndex = 0;
  bool skipReviewed = false;
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _focusNode.requestFocus();
  }

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  void _handleKeyEvent(KeyEvent event) {
    if (event is KeyDownEvent) {
      if (event.logicalKey == LogicalKeyboardKey.arrowRight) {
        _nextFile();
      } else if (event.logicalKey == LogicalKeyboardKey.arrowLeft) {
        _previousFile();
      } else if (event.logicalKey == LogicalKeyboardKey.keyR) {
        _markReviewed();
      }
    }
  }

  void _nextFile() {
    setState(() {
      do {
        currentIndex = (currentIndex + 1) % widget.files.length;
      } while (skipReviewed &&
          widget.files[currentIndex].isReviewed &&
          currentIndex != 0);
    });
  }

  void _previousFile() {
    setState(() {
      do {
        currentIndex =
            (currentIndex - 1 + widget.files.length) % widget.files.length;
      } while (skipReviewed &&
          widget.files[currentIndex].isReviewed &&
          currentIndex != 0);
    });
  }

  void _markReviewed() {
    setState(() {
      widget.files[currentIndex].isReviewed = true;
      _nextFile();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Zen Mode'),
        actions: [
          Row(
            children: [
              const Text('Skip reviewed'),
              Checkbox(
                value: skipReviewed,
                onChanged: (value) {
                  setState(() {
                    skipReviewed = value!;
                  });
                },
              ),
            ],
          ),
        ],
      ),
      body: KeyboardListener(
        focusNode: _focusNode,
        onKeyEvent: _handleKeyEvent,
        child: Row(
          children: [
            Expanded(
              flex: 2,
              child: DiffViewer(file: widget.files[currentIndex]),
            ),
            const VerticalDivider(thickness: 1, width: 1),
            Expanded(
              flex: 1,
              child: NotesPanel(
                file: widget.files[currentIndex],
                onNoteChanged: (String newNote) {
                  setState(() {
                    widget.files[currentIndex].note = newNote;
                  });
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class DiffViewer extends StatelessWidget {
  final DiffFile file;

  const DiffViewer({super.key, required this.file});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Widget>>(
      future: compute(parseDiff, file.content),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.done) {
          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: snapshot.data ?? [],
            ),
          );
        } else {
          return const Center(child: CircularProgressIndicator());
        }
      },
    );
  }
}

List<Widget> parseDiff(String rawDiff) {
  List<Widget> widgets = [];
  List<String> lines = rawDiff.split('\n');
  String currentFile = '';
  FileStatus currentStatus = FileStatus.modified;

  for (String line in lines) {
    if (line.startsWith('diff --git')) {
      currentFile = line.split(' b/').last;
      widgets.add(ListTile(
        title: Text(currentFile,
            style: const TextStyle(fontWeight: FontWeight.bold)),
        leading: Icon(
          currentStatus == FileStatus.modified
              ? Icons.edit
              : currentStatus == FileStatus.added
                  ? Icons.add_circle
                  : Icons.remove_circle,
          color: currentStatus == FileStatus.modified
              ? Colors.orange
              : currentStatus == FileStatus.added
                  ? Colors.green
                  : Colors.red,
        ),
      ));
    } else if (line.startsWith('new file')) {
      currentStatus = FileStatus.added;
    } else if (line.startsWith('deleted file')) {
      currentStatus = FileStatus.deleted;
    } else if (line.startsWith('Binary files')) {
      widgets.add(const Text('Binary file changed',
          style: TextStyle(fontStyle: FontStyle.italic)));
    } else if (line.startsWith('+++') || line.startsWith('---')) {
      // Skip these lines
      continue;
    } else if (line.startsWith('@@')) {
      widgets.add(Container(
        color: Colors.blue[100],
        child: Text(line),
      ));
    } else if (line.startsWith('+')) {
      widgets.add(Container(
        color: Colors.green[100],
        child: Text(line),
      ));
    } else if (line.startsWith('-')) {
      widgets.add(Container(
        color: Colors.red[100],
        child: Text(line),
      ));
    } else {
      widgets.add(Text(line));
    }
  }

  return widgets;
}

DiffReview parseDiffReview(Map<String, dynamic> data) {
  List<String> lines = data['content'].split('\n');
  List<DiffFile> files = [];
  String currentFileName = '';
  List<String> currentFileContent = [];
  FileStatus currentStatus = FileStatus.modified;
  Uint8List? binaryContent;

  for (String line in lines) {
    if (line.startsWith('diff --git')) {
      if (currentFileName.isNotEmpty) {
        files.add(DiffFile(
          name: currentFileName,
          content: currentFileContent.join('\n'),
          status: currentStatus,
          binaryContent: binaryContent,
        ));
        currentFileContent.clear();
        binaryContent = null;
      }
      currentFileName = line.split(' b/').last;
      currentStatus = FileStatus.modified;
    } else if (line.startsWith('new file')) {
      currentStatus = FileStatus.added;
    } else if (line.startsWith('deleted file')) {
      currentStatus = FileStatus.deleted;
    } else if (line.startsWith('Binary files')) {
      // For binary files, we need to extract the content separately
      // This is a placeholder for where you would extract binary content
      binaryContent =
          Uint8List(0); // Placeholder, replace with actual binary content
    } else {
      currentFileContent.add(line);
    }
  }

  // Add the last file
  if (currentFileName.isNotEmpty) {
    files.add(DiffFile(
      name: currentFileName,
      content: currentFileContent.join('\n'),
      status: currentStatus,
      binaryContent: binaryContent,
    ));
  }

  return DiffReview(
    name: data['name'],
    files: files,
  );
}

class DiffViewerScreen extends StatelessWidget {
  final DiffFile file;

  const DiffViewerScreen({super.key, required this.file});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(file.name),
      ),
      body: file.binaryContent != null
          ? _buildBinaryPreview()
          : DiffViewer(file: file),
    );
  }

  Widget _buildBinaryPreview() {
    if (file.name.toLowerCase().endsWith('.png') ||
        file.name.toLowerCase().endsWith('.jpg') ||
        file.name.toLowerCase().endsWith('.jpeg')) {
      return Image.memory(file.binaryContent!);
    } else {
      return const Center(child: Text('Binary file (preview not available)'));
    }
  }
}

List<DiffReview> parseSavedReviews(List<String> savedReviews) {
  return savedReviews.map((reviewString) {
    final reviewData = jsonDecode(reviewString);
    return DiffReview(
      name: reviewData['name'],
      files: (reviewData['files'] as List)
          .map((fileData) => DiffFile(
                name: fileData['name'],
                content: fileData['content'],
                isReviewed: fileData['isReviewed'],
                note: fileData['note'],
                status: FileStatus.modified,
              ))
          .toList(),
    );
  }).toList();
}

class DiffReview {
  final String name;
  final List<DiffFile> files;

  DiffReview({required this.name, required this.files});
}

class DiffFile {
  final String name;
  final String content;
  final FileStatus status;
  bool isReviewed;
  String? note;
  Uint8List? binaryContent;

  DiffFile({
    required this.name,
    required this.content,
    required this.status,
    this.isReviewed = false,
    this.note,
    this.binaryContent,
  });
}

enum FileStatus {
  modified,
  added,
  deleted,
}

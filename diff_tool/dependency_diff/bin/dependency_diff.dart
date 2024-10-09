import 'dart:io';

import 'package:args/args.dart';
import 'package:dependency_diff/dependency_diff.dart' as dependency_diff;
import 'package:dolumns/dolumns.dart';

class Config {
  Config({
    required this.baseBranch,
    required this.comparisonBranch,
    this.repoPath = '/Users/francois/Repos/komodo/komodo-wallet',
  });
  final String baseBranch;
  final String comparisonBranch;
  final String repoPath;
}

void main(List<String> arguments) async {
  final parser = ArgParser()
    ..addOption(
      'baseBranch',
      abbr: 'b',
      help: 'The base branch to compare against.',
      mandatory: true,
    )
    ..addOption(
      'comparisonBranch',
      abbr: 'c',
      help: 'The branch to compare with the base branch.',
      mandatory: true,
    )
    ..addOption(
      'repoPath',
      abbr: 'r',
      defaultsTo: '/Users/francois/Repos/komodo/komodo-wallet',
      help: 'The path to the repository',
    );

  try {
    final argResults = parser.parse(arguments);

    final config = Config(
      baseBranch: argResults['baseBranch'] as String,
      comparisonBranch: argResults['comparisonBranch'] as String,
      repoPath: argResults['repoPath'] as String,
    );

    final String baseFileContent =
        await _getFileFromBranch(config.repoPath, config.baseBranch);
    final String comparisonFileContent =
        await _getFileFromBranch(config.repoPath, config.comparisonBranch);

    final yaml1Packages = dependency_diff.packagesFromString(baseFileContent);
    final yaml2Packages =
        dependency_diff.packagesFromString(comparisonFileContent);
    final diff = dependency_diff.yamlDiff(yaml1Packages, yaml2Packages);

    if (diff.isEmpty) {
      print('The files are identical.');
    } else {
      print('Difference between the files:');
      print(dolumnify(diff));

      // Delete the second row and write to CSV file
      diff.removeAt(1);
      final String csv = diff.map((row) => row.join(',')).join('\n');
      File('diff.csv').writeAsStringSync(csv);
    }
  } catch (e, s) {
    print('Error: $e');
    print(s);
    print(parser.usage);
  }
}

Future<String> _getFileFromBranch(String repoPath, String branch) async {
  final result = await Process.run(
    'git',
    ['show', '$branch:pubspec.lock'],
    workingDirectory: repoPath,
  );
  if (result.exitCode != 0) {
    throw Exception(
      'Failed to retrieve pubspec.lock from branch "$branch" in repository "$repoPath": ${result.stderr}',
    );
  }
  return result.stdout as String;
}

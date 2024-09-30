import 'dart:io';

import 'package:yaml/yaml.dart';

import 'models/package.dart';

export 'models/package.dart';
export 'models/description.dart';

List<List<String>> yamlDiff(
  Map<String, Package> basePackages,
  Map<String, Package> modifiedPackages,
) {
  final diff = <List<String>>[];

  diff.add([
    'Package',
    'Status',
    'Old Version',
    'New Version',
    'Dependency',
    'Old SHA256',
    'New SHA256'
  ]);
  diff.add([
    '-------',
    '------',
    '-----------',
    '-----------',
    '----------',
    '----------',
    '----------'
  ]);

  for (final key in basePackages.keys) {
    final String baseVersion = basePackages[key]?.version ?? '';
    final String modifiedVersion = modifiedPackages[key]?.version ?? '';
    final String dependency = basePackages[key]?.dependency ?? '';
    final String baseSha = basePackages[key]?.description.sha256 ?? '';
    final String modifiedSha = modifiedPackages[key]?.description.sha256 ?? '';
    if (modifiedPackages.containsKey(key)) {
      if (basePackages[key] != modifiedPackages[key]) {
        diff.add(
          [
            key,
            'updated',
            baseVersion,
            modifiedVersion,
            dependency,
            baseSha,
            modifiedSha,
          ],
        );
      }
    } else {
      diff.add([key, 'Removed', baseVersion, '-', dependency, baseSha, '-']);
    }
  }

  for (final key in modifiedPackages.keys) {
    if (!basePackages.containsKey(key)) {
      final String version = modifiedPackages[key]?.version ?? '';
      final String dependency = modifiedPackages[key]?.dependency ?? '';
      final String modifiedSha =
          modifiedPackages[key]?.description.sha256 ?? '';
      diff.add([key, 'Added', '-', version, dependency, '-', modifiedSha]);
    }
  }

  return diff;
}

Map<String, Package> packagesFromFile(String filePath) {
  File file = File(filePath);
  if (!file.existsSync()) {
    throw Exception('File not found: $filePath');
  }

  String lines = file.readAsStringSync();
  final yaml = loadYaml(lines);
  final yamlPackages = yaml['packages'];
  Map<String, Package> packages = {};
  for (var key in yamlPackages.keys) {
    packages[key] = Package.fromYaml(yamlPackages[key]);
  }
  return packages;
}

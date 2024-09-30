import 'dart:io';

import 'package:dependency_diff/dependency_diff.dart' as dependency_diff;
import 'package:dolumns/dolumns.dart';

void main(List<String> arguments) {
  if (arguments.length != 2) {
    print('Please provide the paths of two files as arguments.');
    return;
  }

  String baseFile = arguments[0];
  String modifiedFile = arguments[1];

  final yaml1Packages = dependency_diff.packagesFromFile(baseFile);
  final yaml2Packages = dependency_diff.packagesFromFile(modifiedFile);
  final diff = dependency_diff.yamlDiff(yaml1Packages, yaml2Packages);

  if (diff.isEmpty) {
    print('The files are identical.');
  } else {
    print('Difprint(table(diff));ference between the files:');
    print(dolumnify(diff));
    // delete the second row and write to csv file
    diff.removeAt(1);
    String csv = diff.map((row) => row.join(',')).join('\n');
    File('diff.csv').writeAsStringSync(csv);
  }
}

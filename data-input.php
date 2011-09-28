<?php
/*
 * data-input.php --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2009,2010,2011 Arun Persaud
 *
 * ------------------------------------------------------------------------
 *
 * UNO-darmstadt is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * UNO-darmstadt is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see http://www.gnu.org/licenses/.  *
 *
 * ------------------------------------------------------------------------
 *
 *  wep-page:
 *     http://uno-darmstadt.sourceforge.net
 *
 *  It would be nice to get some feedback (bugs or other comments), so please drop
 *  me a line if you are using UNO-darmstadt :)
 *  have fun
 *        Arun
 */

include('config.php');
include('include/functions.php');

/*
 * open database
 */
if( $db = mysql_connect($DB_HOST,$DB_USER, $DB_PASSWD) )
  {
    mysql_select_db($DB_DB) or die('Could not select database');
  }
 else
   die (mysql_error());

/* generate token */

/* todo add better token that has random bits in it, this one is good for a day...
 * not sure if token is needed at all or adds anything to the security, need to rethink this at one point
 */
$token = md5(date("z")."uno-admin by Arun");

if(myisset('token', 'what')) // and test for token
  {
    /* update DB */
    $newtoken = $_REQUEST['token'];
    $what = trim($_REQUEST['what']);

    switch($what){
    case 'locations':
      $id = $_REQUEST['id'];
      $loc = trim($_REQUEST['2']);
      $coord = trim($_REQUEST['3']);
      $time = trim($_REQUEST['4']);

      /* validation */
      $ok=1;
      if(!is_numeric($id)) $ok=-1;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$loc)) $ok=-2;
      if(!preg_match('/^\s*$/',$coord)) $ok=-3;
      if(!preg_match('/^\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}$/',$time)) $ok=-4;

      if($ok==1)
	{
	  /* check if id exists */
	  $db_id = DB_query_array("SELECT id,create_date,name,X(coordinates),Y(coordinates) from locations where id=$id");
	  if ($db_id)
	    {
	      /* make backup of old value in extra db */
	      $backup = "location: id:".$db_id[0]." date:".$db_id[1]." name:".$db_id[2]." X:".$db_id[3]." Y:".$db_id[4];
	      DB_query("INSERT INTO backup VALUES (NULL, NULL, '$backup')");
	      /* change value */
	      DB_query("UPDATE locations SET create_date = '$time' WHERE id=$id");
	      DB_query("UPDATE locations SET name = '$loc' WHERE id=$id");

	      echo "updated";
	    }
	  else
	    {
	      /* create new entry */
	      DB_query("INSERT INTO locations VALUES (NULL, NULL, '$loc',NULL)");
	      echo "created";
	    }
	}
      else
	echo "incorrect input $ok";

      break;
    case 'players':
      $id = $_REQUEST['id'];
      $name = trim($_REQUEST['2']);
      $time = trim($_REQUEST['3']);

      /* validation */
      $ok=1;
      if(!is_numeric($id)) $ok=-1;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$name)) $ok=-2;
      if(!preg_match('/^\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}$/',$time)) $ok=-3;

      if($ok==1)
	{
	  /* check if id exists */
	  $db_id = DB_query_array("SELECT id,create_date,name from players where id=$id");
	  if ($db_id)
	    {
	      /* make backup of old value in extra db */
	      $backup = "players: id:".$db_id[0]." date:".$db_id[1]." name:".$db_id[2];
	      DB_query("INSERT INTO backup VALUES (NULL, NULL, '$backup')");
	      /* change value */
	      DB_query("UPDATE players SET create_date = '$time' WHERE id=$id");
	      DB_query("UPDATE players SET name = '$name' WHERE id=$id");

	      echo "updated";
	    }
	  else
	    {
	      /* create new entry */
	      DB_query("INSERT INTO players VALUES (NULL, NULL, '$name')");
	      echo "created";
	    }
	}
      else
	echo "incorrect input $ok";

      break;
    case 'variations':
      $id = $_REQUEST['id'];
      $name  = trim($_REQUEST['2']);
      $short = trim($_REQUEST['3']);
      $time  = trim($_REQUEST['4']);

      /* validation */
      $ok=1;
      if(!is_numeric($id)) $ok=-1;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$name)) $ok=-2;
      if(!preg_match('/^[a-zA-Z0-9 ]*$/',$short)) $ok=-3;
      if(!preg_match('/^\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2}$/',$time)) $ok=-4;

      if($ok==1)
	{
	  /* check if id exists */
	  $db_id = DB_query_array("SELECT id,create_date,name,short from variations where id=$id");
	  if ($db_id)
	    {
	      /* make backup of old value in extra db */
	      $backup = "variations: id:".$db_id[0]." date:".$db_id[1]." name:".$db_id[2]." short:".$db_id[3];
	      DB_query("INSERT INTO backup VALUES (NULL, NULL, '$backup')");
	      /* change value */
	      DB_query("UPDATE variations SET create_date = '$time' WHERE id=$id");
	      DB_query("UPDATE variations SET name  = '$name' WHERE id=$id");
	      DB_query("UPDATE variations SET short = '$short' WHERE id=$id");

	      echo "updated";
	    }
	  else
	    {
	      /* create new entry */
	      DB_query("INSERT INTO variations VALUES (NULL, NULL, '$name','$short')");
	      echo "created";
	    }
	}
      else
	echo "incorrect input $ok";

      break;
    case 'game':
      $variation = $_REQUEST['variation'];
      $location  = $_REQUEST['location'];
      $date      = trim($_REQUEST['date']);

      for($nplayer=0;myisset('player'.$nplayer); $nplayer++);
      for($ngames=0;myisset('game-'.$ngames.'-0'); $ngames++);

      /* check for end with black card */
      $ewbc = array();
      for($i=0; $i<$ngames; $i++)
	$ewbc[$i] = myisset('ewbc'.$i);

      /* find player ids */
      $players = array();
      for($i=0; $i<$nplayer; $i++)
	$players[$i] = $_REQUEST['player'.$i];

      /* validation */
      $ok=1;
      if(!is_numeric($variation)) $ok=-1;
      if(!is_numeric($location)) $ok=-2;
      if(!preg_match('/^\d{4}-\d{2}-\d{2}$/',$date)) $ok=-3;

      /* players id needs to be a number */
      for($i=0; $i<$nplayer; $i++)
	if(!is_numeric($players[$i])) $ok=-4;

      /* game result needs to be a number or "-", each game needs to have exactly one "-" */
      for($j=0; $j<$ngames; $j++)
	{
	  $gotwinner=0;
	  for($i=0; $i<$nplayer; $i++)
	    {
	      if(!preg_match('/^[0-9\-]*$/', $_REQUEST['game-'.$j.'-'.$i])) $ok=-5;
	      if($_REQUEST['game-'.$j.'-'.$i]=="-")
		$gotwinner++;
	    }
	  if($gotwinner!=1) $ok=-5.5;
	}

      /* player id can only show up once */
      for($i=0; $i<$nplayer; $i++)
	for($j=$i+1; $j<$nplayer; $j++)
	  if($players[$i]==$players[$j]) $ok=-6;

      /* ids of location, variations and players must exist */
      for($i=0; $i<$nplayer; $i++)
	{
	  $db_id = DB_query_array("SELECT id from players where id=".$players[$i]);
	  if (!$db_id) $ok=-7;
	};
      $db_id = DB_query_array("SELECT id from variations where id=$variation");
      if (!$db_id) $ok=-7;
      $db_id = DB_query_array("SELECT id from locations where id=$location");
      if (!$db_id) $ok=-7;

      if($ok==1)
	{
	  /* everything ok, submit to database */

	  /* create session */
	  echo "INSERT INTO session VALUES (NULL, $date, $location, $nplayer, NULL, $variation) <br/>";
	  DB_query_array("INSERT INTO session VALUES (NULL, $date, $location, $nplayer, NULL, $variation)");
	  $session_id = mysql_insert_id();

	  /* keep track of score, since we need to calculate the differences for each single score */
	  for($j=0; $j<$nplayer; $j++)
	    $lastscore[$j]=0;

	  /* create games */
	  for($i=0;$i<$ngames; $i++)
	    {
	      /* create game id */
	      echo "INSERT INTO games VALUES (NULL, $session_id, ".$ewbc[$i]." ) <br />";
	      DB_query_array("INSERT INTO games VALUES (NULL, $session_id, ".$ewbc[$i]." )");
	      $game_id = mysql_insert_id();

	      for($j=0; $j<$nplayer; $j++)
		{
		  $score = $_REQUEST['game-'.$i.'-'.$j];
		  /* mark winner */
		  if($score=="-")
		    $score = -9999;
		  else
		    $score = $score - $oldscore[$j];

		  DB_query_array("INSERT INTO scores VALUES (NULL, $game_id, ".$players[$j].",$score, $j )");
		  //echo " game $i: position: $j player:".$players[$j]." score: $score <br/>";

		  /* remember old score */
		  if($score!=-9999)
		    $oldscore[$j] = $_REQUEST['game-'.$i.'-'.$j];

		}
	    }

	  echo "submitted to database";
	}
      else
	echo "Validation error: $ok";

      break;
    }
  }
else
  {
    //output html
    // check tmp.tmp to see what needs to be implemented
    output_header();
?>

<p>After changing/adding locations or players names you need to reload to be able to use them in the game input!</p>
<p>There is some error checking on the input, but double check before you hit "save" or "submit".</p>
<p>Entering coordinates is not supported at the moment (field needs to be empty).</p>

<ul class="datainput">
<li class="locations"> <button class="toggle">show/edit locations</button>
<?php
	 echo "<table class=\"stats\" >\n";
	 echo "<thead><tr><th>ID</th><th>Name</th><th>Coordinates</th><th>created</th><th></th></tr></thead>\n";
	 echo "<tbody>\n";
         $datatmp = mysql_query("SELECT id,create_date,name,X(coordinates), Y(coordinates) FROM locations ORDER BY name");
	 while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $id = $dat[0];
	     $date  = $dat[1];
	     $name  = $dat[2];
	     $coorX  = $dat[3];
	     $coorY  = $dat[4];
	     echo "<tr><td>$id</td> <td>$name</td><td>$coorX $coorY</td> <td>$date</td> <td><button class=\"edit\">edit</button></td></tr>\n";
	   }
	 echo "<tr><td></td> <td></td><td></td> <td></td> <td><button class=\"edit\">new</button></td></tr>\n";
	 echo "</tbody></table>\n</div>\n";
?>
<li class="players"> <button class="toggle">show/edit players</button>
<?php
	 echo "<table class=\"stats\" >\n";
	 echo "<thead><tr><th>ID</th><th>Name</th><th>created</th><th></th></tr></thead>\n";
	 echo "<tbody>\n";
         $datatmp = mysql_query("SELECT * FROM players ORDER BY name");
	 while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $id = $dat[0];
	     $date  = $dat[1];
	     $name  = $dat[2];
	     echo "<tr><td>$id</td> <td>$name</td> <td>$date</td> <td><button class=\"edit\">edit</button></td></tr>\n";
	   }
	 echo "<tr><td></td> <td></td><td></td> <td><button class=\"edit\">new</button></td></tr>\n";
	 echo "</tbody></table>\n</div>\n";
?>
<li class="variations"> <button class="toggle">add/edit variations </button>
<?php
	 echo "<table class=\"stats\" >\n";
	 echo "<thead><tr><th>ID</th><th>Name</th><th>short</th><th>created</th><th></th></tr></thead>\n";
	 echo "<tbody>\n";
         $datatmp = mysql_query("SELECT * FROM variations");
	 while($dat= mysql_fetch_array($datatmp, MYSQL_NUM))
	   {
	     $id = $dat[0];
	     $date  = $dat[1];
	     $name  = $dat[2];
	     $short  = $dat[3];
	     echo "<tr><td>$id</td> <td>$name</td> <td>$short</td> <td>$date</td> <td><button class=\"edit\">edit</button></td></tr>\n";
	   }
	 echo "<tr><td></td> <td></td> <td></td> <td></td> <td><button class=\"edit\">new</button></td></tr>\n";
	 echo "</tbody></table>\n</div>\n";
?>
<li class="game"> <button class="gametoggle">add game</button>
<form action="data-input.php" method="post">
<input type="hidden" name="token" value="<?php echo $token; ?>">
<input type="hidden" name="what"  value="game">
<label for="variation"> Variation:</label> <select name='variation' id='variation'>
<?php
 $datatmp = mysql_query("SELECT id,name FROM variations");
 while ($temp = mysql_fetch_assoc($datatmp))
  {
    echo "<option value='".$temp['id']."'>".$temp['name']."</option>\n";
  }
?>
</select><br />
<label for="location"> Location:</label> <select name='location' id='location'>
<?php
 $datatmp = mysql_query("SELECT id,name FROM locations");
 while ($temp = mysql_fetch_assoc($datatmp))
  {
    echo "<option value='".$temp['id']."'>".$temp['name']."</option>\n";
  }
?>
</select> <br />
<label for="date"> Date:</label><input type='date' name='date' id='date' placeholder='yyyy-mm-dd'>
<p>Input points that are summed up already!</p>
<table class="stats">
<thead>
  <tr><th>End with black card</th> <th><button class="newplayer">new player</button></th></tr>
</thead>
<tbody>
  <tr> <td><input type="checkbox" name="ewbc0" value="ewbc" /></td> <td><button class="newgame">new row</button></td> </tr>
</tbody>
</table>
<input type="submit" value="Submit" />
</form>

</ul>

<script>


$(".game form").submit(function(event) {

    /* stop form from submitting normally */
    event.preventDefault();

    $.post("data-input.php",$(".game form").serialize(),
           function(data){ $('ul').before("<p>"+data+"</p>").prev().css('background-color','red').fadeOut(10000) },
           'html');

  });

/* gives a selector with all possible names */
function printselectplayer(i) {
   var html = "<select name=\"player"+(i-2)+"\">\n";
<?php
 $datatmp = mysql_query("SELECT id,name FROM players");
 while ($temp = mysql_fetch_assoc($datatmp))
  {
    echo 'html += "<option value=\''.$temp['id']."'>".$temp['name']."</option>\\n\";\n";
  }
?>
   html += "</select>\n";
   return html;
 }

/* update numeric input names */
 function updateinput() {
   $('input[type="number"]').each(function(i) { $(this).removeAttr("name"); });
   $('input[type="number"]').each(function(i) { $(this).attr("name",i ); });
 }

/* adds a column to a game table */
function addCol() {
    var currentNumberOfTDsInARow = $('.game table tr:last td').length;
    newColNum = currentNumberOfTDsInARow;
    var rows = $('.game tbody tr');
    $('.game thead tr').find('th:last').html(printselectplayer(newColNum));
    $('.game thead tr').find('th:last').after('<th><button class="newplayer">new player</button></th>');
    for (var i = 0; i < rows.length; i++) {
        $(rows[i]).find('td:last').before('<td><input type="text" name="game-'+i+'-'+(newColNum-2)+'"></td>');
    }
    $(".newplayer").click(addCol);
    updateinput();
}
$(".newplayer").click(addCol);

/* adds a row to a game table */
function addRow() {
  var currentNumberOfRows = $('.game table tr').length -1;
  $('.game tbody tr').find('td:last').html('');
  var row = "<tr><td><input type=\"checkbox\" name=\"ewbc"+$('.game tbody tr').length+"\" value=\"ewbc\" /></td>";
  $('.game tbody tr:last').find('td:not(:first-child, :last-child)').each( function(index) {
      row = row.concat("<td><input type=\"text\" name=\"game-"+currentNumberOfRows+"-"+index+"\"></td> ") } );
  row=row.concat("<td><button class=\"newgame\">new row</button></td></tr>\n");

  $('.game tbody:last').append(row);
  $(".newgame").click(addRow);
  updateinput();
}
$(".newgame").click(addRow);

function tableedit() {
    mynewbutton = '<button class="save">save</button><button class="cancel">cancel</button>';
    myoldbutton = '<button class="edit">edit</button>';

    var table = $(this).parent().parent()

    var mycont= new Array();

    /* remember current content */
    table.find("td").each( function(index) { mycont[index]=$(this).html(); } );

    /* replace with input elements, skip first and last */
    table.find('td:not(:first-child, :last-child)').each( function(index) { $(this).html('<input type="text" value="'+ mycont[index+1] +'">')} )

    table.find("td:last-child").html(mynewbutton);
    $(".edit").attr("disabled", "disabled");

    /* add functions to exit edit */
    table.find("td:last-chile").find(".cancel").click(function () {

    var table = $(this).parent().parent();

    table.find('td:not(:first-child, :last-child)').each( function(index) { $(this).html(mycont[index+1])} );
    $(".edit").removeAttr("disabled");
    table.find("td:last-child").html(mycont[mycont.length-1]).find(".edit").click(tableedit);

    });
    table.find("td:last-child").find(".save").click(function () {

       var table = $(this).parent().parent();

       token = <?php echo '"'.$token.'"' ?> ;
       var myclass = $(this).closest("li").attr('class');
       var mydata = {};
       var datanew = {};

       /* update content */
       table.find("td input").each( function(index) { datanew[index]=$(this).attr("value"); } );

       var i,j=0;
       mydata.what  = myclass;
       mydata.token = token;
       mydata.id    = mycont[0];
       j=2;
       for(i in mycont)
	 {mydata[j]=datanew[i];j++;}

       $.post("data-input.php",mydata,
              function(data){ $('ul').before("<p>"+data+"</p>").prev().css('background-color','red').fadeOut(10000) },
              'html');

       /* reset to new values */
       table.find('td:not(:first-child, :last-child)').each( function(index) { $(this).html(datanew[index])} );
       $(".edit").removeAttr("disabled");
       table.find("td:last-child").html(myoldbutton);

       /* if no id, add new row */
       var row = "<tr>";
       table.find('td:not(:last-child)').each( function(index) { row = row.concat("<td></td> ") } );
       row=row.concat("<td><button class=\"edit\">new</button></td></tr>");
       if(mycont[0].length===0)
	 {
	   table.closest('table').find('tbody:last').append(row);
	 }
       $(".edit").click(tableedit);

    });

}

$(".toggle").click(function ()     {   $(this).parent().find("table").toggle(); });
$(".gametoggle").click(function () {   $(this).parent().find("form").toggle(); });
$(".edit").click(tableedit);


</script>


<?php
output_footer();
  } // end if-else html output
?>
